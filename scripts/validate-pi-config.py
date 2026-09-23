#!/usr/bin/env python3
"""Static, read-only validation for the repository-managed Pi payload."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


EXPECTED_PACKAGES = {
    "git:github.com/obra/superpowers",
    "npm:pi-mcp-adapter",
}
EXPECTED_MODELS = {
    ("bifrost", "huggingface/deepinfra/deepseek-ai/DeepSeek-V4-Pro"),
    ("bifrost-openai", "gpt-5.6-luna"),
}
EXPECTED_ENDPOINTS = {
    "https://bifrost.ops.gorgias.io/v1",
    "https://bifrost.ops.gorgias.io/openai/v1",
}
SECRET_PATTERNS = (
    re.compile(r"(?:sk|key|token|secret)[-_][A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
)


class ValidationError(ValueError):
    """Raised for a malformed or unsafe Pi configuration payload."""


def _walk_strings(value: Any, path: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_mapping(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return {}
    return value


def _validate_secret_free(payloads: dict[str, Any], errors: list[str]) -> None:
    for payload_name, payload in payloads.items():
        for path, value in _walk_strings(payload):
            if value == "$BIFROST_VIRTUAL_KEY":
                continue
            if any(pattern.search(value) for pattern in SECRET_PATTERNS):
                errors.append(f"{payload_name}.{path} contains a literal credential")


def _validate_models(models: Any, errors: list[str]) -> None:
    root = _require_mapping(models, "models", errors)
    providers = _require_mapping(root.get("providers"), "models.providers", errors)
    found: set[tuple[str, str]] = set()
    seen: set[tuple[str, str]] = set()

    for provider_id, provider_value in providers.items():
        provider_path = f"models.providers.{provider_id}"
        provider = _require_mapping(provider_value, provider_path, errors)
        endpoint = provider.get("baseUrl")
        if endpoint not in EXPECTED_ENDPOINTS or not str(endpoint).startswith(
            "https://bifrost.ops.gorgias.io/"
        ):
            errors.append(f"{provider_path}.baseUrl must be a catalogued Bifrost endpoint")
        if provider.get("api") != "openai-completions":
            errors.append(f"{provider_path}.api must be openai-completions")
        if provider.get("apiKey") != "$BIFROST_VIRTUAL_KEY":
            errors.append(f"{provider_path}.apiKey must use $BIFROST_VIRTUAL_KEY")
        model_list = provider.get("models")
        if not isinstance(model_list, list) or not model_list:
            errors.append(f"{provider_path}.models must be a non-empty array")
            continue
        for index, model_value in enumerate(model_list):
            model_path = f"{provider_path}.models[{index}]"
            model = _require_mapping(model_value, model_path, errors)
            model_id = model.get("id")
            if not isinstance(model_id, str):
                errors.append(f"{model_path}.id must be a string")
                continue
            identity = (provider_id, model_id)
            if identity in seen:
                errors.append(f"{model_path} duplicates a provider/model identity")
            seen.add(identity)
            found.add(identity)
            for field in ("name", "reasoning", "input", "cost", "contextWindow", "maxTokens"):
                if field not in model:
                    errors.append(f"{model_path}.{field} is required")
            if model.get("reasoning") is not True:
                errors.append(f"{model_path}.reasoning must be true")
            if model.get("input") != ["text"]:
                errors.append(f"{model_path}.input must be [\"text\"]")
            cost = _require_mapping(model.get("cost"), f"{model_path}.cost", errors)
            for cost_field in ("input", "output", "cacheRead", "cacheWrite"):
                if not _is_number(cost.get(cost_field)) or cost[cost_field] < 0:
                    errors.append(f"{model_path}.cost.{cost_field} must be a non-negative number")
            for limit_field in ("contextWindow", "maxTokens"):
                if not isinstance(model.get(limit_field), int) or model[limit_field] <= 0:
                    errors.append(f"{model_path}.{limit_field} must be a positive integer")

    if found != EXPECTED_MODELS:
        errors.append("models must contain exactly the catalogued DeepSeek V4 Pro and Luna entries")


def _validate_settings(settings: Any, errors: list[str]) -> None:
    root = _require_mapping(settings, "settings", errors)
    if root.get("defaultProvider") != "bifrost-openai":
        errors.append("settings.defaultProvider must select the Bifrost Luna provider")
    if root.get("defaultModel") != "gpt-5.6-luna":
        errors.append("settings.defaultModel must be gpt-5.6-luna")
    if root.get("defaultThinkingLevel") not in {"off", "minimal", "low", "medium", "high", "xhigh", "max"}:
        errors.append("settings.defaultThinkingLevel must be a documented Pi thinking level")
    packages = root.get("packages")
    if not isinstance(packages, list) or set(packages) != EXPECTED_PACKAGES or len(packages) != len(EXPECTED_PACKAGES):
        errors.append("settings.packages must contain only the two approved package sources")
    if root.get("enableSkillCommands") is not True:
        errors.append("settings.enableSkillCommands must be true")


def _validate_mcp(mcp: Any, errors: list[str]) -> None:
    root = _require_mapping(mcp, "mcp", errors)
    if root.get("lazy") is not True:
        errors.append("mcp.lazy must be true")
    if root.get("directTools") is not False:
        errors.append("mcp.directTools must be false")
    if root.get("allowInstall") is not False:
        errors.append("mcp.allowInstall must be false")
    servers = root.get("mcpServers")
    if not isinstance(servers, dict) or servers:
        errors.append("mcp.mcpServers must be an empty object until servers are approved")


def validate_payloads(models: Any, settings: Any, mcp: Any) -> list[str]:
    """Return safe, non-secret validation errors for decoded JSON payloads."""

    errors: list[str] = []
    _validate_secret_free({"models": models, "settings": settings, "mcp": mcp}, errors)
    _validate_models(models, errors)
    _validate_settings(settings, errors)
    _validate_mcp(mcp, errors)
    return errors


def _load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ValidationError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: line {exc.lineno} column {exc.colno}") from exc


def validate_root(root: Path) -> list[str]:
    """Read only the three declared files and return validation errors."""

    payloads = {
        "models": _load_json(root / "pi-config" / "models.json"),
        "settings": _load_json(root / "pi-config" / "settings.json"),
        "mcp": _load_json(root / "pi-config" / "mcp.json"),
    }
    return validate_payloads(**payloads)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        errors = validate_root(args.root)
    except ValidationError as exc:
        print(f"FAIL: {exc}")
        return 1
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: Pi configuration is valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
