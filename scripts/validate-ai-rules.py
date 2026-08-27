#!/usr/bin/env python3
"""Validate the cross-artifact contracts used by the ai-rules deployment.

The validator is deliberately read-only.  It can inspect the tracked source
tree directly, or compare that source tree with a staged deployment payload.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - reported as a validation error
    yaml = None


CANONICAL_MCP = "cortex"
CONTEXT7_MCP = "context7"
CONTEXT7_ENDPOINT = "https://mcp.context7.com/mcp"
CONTEXT7_TOKEN_REFERENCE = "{env:CONTEXT7_API_TOKEN}"
CONTEXT7_AGENT = "librarian"
# These are built into the OMO runtime rather than declared in mcp.jsonc.
BUILTIN_MCP_REFERENCES = frozenset({"gh_grep", "websearch"})
# Supplied by the user's OpenCode installation, not vendored into this repo.
EXTERNAL_SKILL_REFERENCES = frozenset({"codebase-memory", "orca-cli"})
NON_MCP_OVERVIEW_ACCESS = frozenset({"agent-browser CLI", "pup CLI"})
REVIEWER_PREFIX = "reviewer-"
REQUIRED_PROFILES = ("default", "cost-efficient")
REVIEWER_CONTRACT_FIELDS = (
    '"critical"',
    '"important"',
    '"suggestions"',
    '"positive"',
    '"errors"',
)


def _has_reviewer_contract_agent(text: str, lane: str) -> bool:
    """Return whether text contains the lane's JSON contract agent field."""

    return re.search(rf'"agent"\s*:\s*"{re.escape(lane)}"', text) is not None


@dataclass
class Artifact:
    path: Path
    text: str
    data: Any


class DuplicateJSONKeyError(ValueError):
    """Raised when a JSON object contains the same key more than once."""

    def __init__(self, key: str) -> None:
        super().__init__(f"duplicate JSON key {key!r}")
        self.key = key


def _line_for_key(text: str, key: str) -> int | None:
    """Return the first useful source line containing a mapping key or value."""

    key_pattern = re.compile(
        rf"(?:^|[\s,{{\[])(?:\"{re.escape(key)}\"|{re.escape(key)})\s*:"
    )
    for line_number, line in enumerate(text.splitlines(), 1):
        if key_pattern.search(line):
            return line_number
    return None


def _line_for_value(text: str, value: str) -> int | None:
    for line_number, line in enumerate(text.splitlines(), 1):
        if value in line:
            return line_number
    return None


def _jsonc_without_comments(text: str) -> str:
    """Remove JSONC comments and trailing commas while preserving line numbers."""

    chars = list(text)
    index = 0
    in_string = False
    escaped = False
    while index < len(chars):
        char = chars[index]
        next_char = chars[index + 1] if index + 1 < len(chars) else ""
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and next_char == "/":
            chars[index] = " "
            chars[index + 1] = " "
            index += 2
            while index < len(chars) and chars[index] not in "\r\n":
                chars[index] = " "
                index += 1
            continue
        if char == "/" and next_char == "*":
            start = index
            chars[index] = " "
            chars[index + 1] = " "
            index += 2
            closed = False
            while index + 1 < len(chars):
                if chars[index] == "*" and chars[index + 1] == "/":
                    chars[index] = " "
                    chars[index + 1] = " "
                    index += 2
                    closed = True
                    break
                if chars[index] not in "\r\n":
                    chars[index] = " "
                index += 1
            if not closed:
                line = text.count("\n", 0, start) + 1
                raise ValueError(f"unterminated block comment at line {line}")
            continue
        index += 1

    cleaned = "".join(chars)
    chars = list(cleaned)
    index = 0
    in_string = False
    escaped = False
    while index < len(chars):
        char = chars[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(chars) and chars[lookahead].isspace():
                lookahead += 1
            if lookahead < len(chars) and chars[lookahead] in "}]":
                chars[index] = " "
        index += 1
    return "".join(chars)


class Validator:
    def __init__(self, root: Path, payload: Path | None):
        self.root = root.resolve()
        self.payload = payload.resolve() if payload else None
        self.errors: list[str] = []

    def display_path(self, path: Path) -> str:
        path = path.resolve()
        for base, prefix in (
            (self.root, ""),
            (self.payload, "payload/") if self.payload else (None, ""),
        ):
            if base is None:
                continue
            try:
                relative = path.relative_to(base)
            except ValueError:
                continue
            return f"{prefix}{relative}" if prefix else str(relative)
        return str(path)

    def add_error(
        self,
        path: Path,
        message: str,
        *,
        line: int | None = None,
        key: str | None = None,
        text: str | None = None,
    ) -> None:
        if line is None and key is not None and text is not None:
            line = _line_for_key(text, key) or _line_for_value(text, key)
        location = f":{line}" if line else ""
        self.errors.append(f"{self.display_path(path)}{location}: {message}")

    def read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            self.add_error(path, f"cannot read file: {error}")
            return None

    def load_json(self, path: Path, *, jsonc: bool = False) -> Artifact | None:
        text = self.read_text(path)
        if text is None:
            return None
        source = text
        if jsonc:
            try:
                source = _jsonc_without_comments(text)
            except ValueError as error:
                self.add_error(path, str(error))
                return None

        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            data: dict[str, Any] = {}
            for key, value in pairs:
                if key in data:
                    raise DuplicateJSONKeyError(key)
                data[key] = value
            return data

        try:
            data = json.loads(source, object_pairs_hook=reject_duplicate_keys)
        except DuplicateJSONKeyError as error:
            self.add_error(path, str(error))
            return None
        except json.JSONDecodeError as error:
            self.add_error(path, error.msg, line=error.lineno)
            return None
        return Artifact(path, text, data)

    def load_yaml(self, path: Path) -> Artifact | None:
        text = self.read_text(path)
        if text is None:
            return None
        if yaml is None:
            self.add_error(path, "PyYAML is required to parse YAML")
            return None
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            line = mark.line + 1 if mark else None
            self.add_error(path, f"invalid YAML: {error}", line=line)
            return None
        return Artifact(path, text, data)

    def require_mapping(
        self, artifact: Artifact | None, label: str
    ) -> dict[str, Any] | None:
        if artifact is None:
            return None
        if not isinstance(artifact.data, dict):
            self.add_error(artifact.path, f"{label} must be a mapping")
            return None
        return artifact.data

    def compare_sets(
        self,
        path: Path,
        label: str,
        expected: Iterable[str],
        actual: Iterable[str],
        *,
        text: str | None = None,
    ) -> None:
        expected_set = set(expected)
        actual_set = set(actual)
        missing = sorted(expected_set - actual_set)
        unknown = sorted(actual_set - expected_set, key=str)
        if missing:
            self.add_error(path, f"{label} missing: {', '.join(missing)}", text=text)
        if unknown:
            unknown_text = ", ".join(str(value) for value in unknown)
            self.add_error(path, f"{label} unknown: {unknown_text}", text=text)

    def validate_mcp_names(
        self, mcp_artifact: Artifact | None
    ) -> tuple[set[str], set[str]]:
        if mcp_artifact is None:
            return set(), set()
        mcp = self.require_mapping(mcp_artifact, "mcp.jsonc")
        if mcp is None:
            return set(), set()
        servers = mcp.get("mcpServers")
        if not isinstance(servers, dict):
            self.add_error(
                mcp_artifact.path,
                "mcpServers must be a mapping",
                key="mcpServers",
                text=mcp_artifact.text,
            )
            return set(), set()
        names = set()
        disabled_names = set()
        for name, specification in servers.items():
            if not isinstance(name, str):
                self.add_error(
                    mcp_artifact.path,
                    "MCP server names must be strings",
                    key="mcpServers",
                    text=mcp_artifact.text,
                )
            else:
                names.add(name)
                if (
                    isinstance(specification, dict)
                    and specification.get("enabled", True) is False
                ):
                    disabled_names.add(name)
        if "context-layer" in names:
            self.add_error(
                mcp_artifact.path,
                "stale MCP name context-layer; use cortex",
                key="context-layer",
                text=mcp_artifact.text,
            )
        if CANONICAL_MCP not in names:
            self.add_error(
                mcp_artifact.path,
                "canonical MCP server cortex is missing",
                key="mcpServers",
                text=mcp_artifact.text,
            )
        return names - disabled_names, disabled_names

    def validate_context7_mcp(self, artifact: Artifact | None) -> None:
        """Validate the source Context7 server's transport and credentials."""

        if artifact is None:
            return
        mcp = self.require_mapping(artifact, "mcp.jsonc")
        if mcp is None:
            return
        servers = mcp.get("mcpServers")
        if not isinstance(servers, dict):
            return
        specification = servers.get(CONTEXT7_MCP)
        if specification is None:
            self.add_error(
                artifact.path,
                "Context7 MCP server context7 is missing",
                key="mcpServers",
                text=artifact.text,
            )
            return
        if not isinstance(specification, dict):
            self.add_error(
                artifact.path,
                "mcpServers.context7 must be a mapping",
                key=CONTEXT7_MCP,
                text=artifact.text,
            )
            return

        if specification.get("enabled") is not True:
            self.add_error(
                artifact.path,
                "Context7 MCP server context7 must be enabled",
                key=CONTEXT7_MCP,
                text=artifact.text,
            )

        if specification.get("type") != "http":
            self.add_error(
                artifact.path,
                "Context7 MCP server must use the HTTP (Streamable HTTP) transport",
                key="type",
                text=artifact.text,
            )

        if specification.get("url") != CONTEXT7_ENDPOINT:
            self.add_error(
                artifact.path,
                f"Context7 MCP server must use endpoint {CONTEXT7_ENDPOINT!r}",
                key="url",
                text=artifact.text,
            )

        headers = specification.get("headers")
        if not isinstance(headers, dict):
            self.add_error(
                artifact.path,
                "Context7 MCP server headers must be a mapping containing environment-only authentication",
                key="headers",
                text=artifact.text,
            )
            return

        expected_authorization = f"Bearer {CONTEXT7_TOKEN_REFERENCE}"

        def uses_context7_token(value: Any) -> bool:
            return value in (
                CONTEXT7_TOKEN_REFERENCE,
                expected_authorization,
            )

        if headers != {"Authorization": expected_authorization}:
            self.add_error(
                artifact.path,
                "Context7 MCP server headers must contain exactly Authorization: Bearer {env:CONTEXT7_API_TOKEN}",
                key="headers",
                text=artifact.text,
            )

        for name, value in headers.items():
            normalized_name = (
                name.lower().replace("_", "-") if isinstance(name, str) else ""
            )
            if (
                normalized_name == "authorization"
                or "api-key" in normalized_name
                or "api-token" in normalized_name
                or normalized_name == "token"
            ) and (
                not uses_context7_token(value)
            ):
                self.add_error(
                    artifact.path,
                    f"Context7 MCP credential header {name!r} must use environment-only authentication",
                    key=name,
                    text=artifact.text,
                )

    def validate_context7_rule(self) -> None:
        """Validate the canonical Context7 workflow guidance."""

        path = self.root / ".rulesync" / "rules" / "context7.md"
        text = self.read_text(path)
        if text is None:
            return

        resolve_position = text.find("resolve-library-id")
        query_position = text.find("query-docs")
        if resolve_position == -1 or query_position == -1:
            self.add_error(
                path,
                "canonical Context7 rule must describe resolve-library-id followed by query-docs",
                key="Context7",
                text=text,
            )
        elif resolve_position > query_position:
            self.add_error(
                path,
                "canonical Context7 rule must describe resolve-library-id before query-docs",
                key="query-docs",
                text=text,
            )

        requirements = (
            (
                re.compile(r"single[- ]concept|one concept", re.IGNORECASE),
                "canonical Context7 rule must scope query-docs requests to a single concept",
                "single concept",
            ),
            (
                re.compile(r"/org/project/version"),
                "canonical Context7 rule must document the versioned library ID format /org/project/version",
                "/org/project/version",
            ),
            (
                re.compile(r"fallback|unavailable", re.IGNORECASE),
                "canonical Context7 rule must describe fallback behavior when the service is unavailable",
                "fallback",
            ),
            (
                re.compile(
                    r"disclos|say\s+so\s+explicitly|could not be fetched|"
                    r"unable to fetch|not available|do not claim.*fetched",
                    re.IGNORECASE,
                ),
                "canonical Context7 rule must disclose when current documentation could not be fetched",
                "disclose",
            ),
        )
        for pattern, message, key in requirements:
            if pattern.search(text) is None:
                self.add_error(path, message, key=key, text=text)

    def validate_mcp_references(
        self,
        references: Iterable[tuple[Path, str, list[Any], str]],
        server_names: set[str],
        disabled_server_names: set[str],
    ) -> None:
        for path, location, values, text in references:
            for index, value in enumerate(values):
                if not isinstance(value, str):
                    self.add_error(
                        path,
                        f"{location}[{index}] must be a string",
                        key=location.split(".")[-1],
                        text=text,
                    )
                    continue
                if value == "context-layer":
                    self.add_error(
                        path,
                        f"{location}[{index}] uses stale MCP name context-layer; use cortex",
                        key=value,
                        text=text,
                    )
                elif value in BUILTIN_MCP_REFERENCES:
                    continue
                elif value in disabled_server_names:
                    self.add_error(
                        path,
                        f"{location}[{index}] references disabled MCP {value!r}",
                        key=value,
                        text=text,
                    )
                elif value not in server_names:
                    self.add_error(
                        path,
                        f"{location}[{index}] references unknown MCP {value!r}",
                        key=value,
                        text=text,
                    )

    def collect_omo_agents(
        self,
        artifact: Artifact,
    ) -> tuple[
        dict[str, dict[str, Any]],
        list[tuple[Path, str, list[Any], str]],
        list[tuple[Path, str, list[Any], str]],
    ]:
        config = self.require_mapping(artifact, "oh-my-opencode-slim.json")
        if config is None:
            return {}, [], []
        disabled = config.get("disabled_agents", [])
        if isinstance(disabled, list):
            disabled = {value for value in disabled if isinstance(value, str)}
        else:
            self.add_error(
                artifact.path,
                "disabled_agents must be a list",
                key="disabled_agents",
                text=artifact.text,
            )
            disabled = set()
        agents: dict[str, dict[str, Any]] = {}
        mcp_references = []
        skill_references = []

        presets = config.get("presets")
        if not isinstance(presets, dict):
            self.add_error(
                artifact.path,
                "presets must be a mapping",
                key="presets",
                text=artifact.text,
            )
        else:
            active_preset = config.get("preset", "bifrost")
            if not isinstance(active_preset, str) or not active_preset:
                self.add_error(
                    artifact.path,
                    "preset must be a non-empty string",
                    key="preset",
                    text=artifact.text,
                )
            else:
                active_preset_specification = presets.get(active_preset)
                if not isinstance(active_preset_specification, dict):
                    self.add_error(
                        artifact.path,
                        f"presets.{active_preset} must be a mapping",
                        key=active_preset,
                        text=artifact.text,
                    )
                else:
                    self._collect_agent_section(
                        artifact,
                        active_preset_specification,
                        f"presets.{active_preset}",
                        agents,
                        disabled,
                        mcp_references,
                        skill_references,
                    )

        custom = config.get("agents")
        if not isinstance(custom, dict):
            self.add_error(
                artifact.path,
                "agents must be a mapping",
                key="agents",
                text=artifact.text,
            )
        else:
            self._collect_agent_section(
                artifact,
                custom,
                "agents",
                agents,
                disabled,
                mcp_references,
                skill_references,
            )
        return agents, mcp_references, skill_references

    def _collect_agent_section(
        self,
        artifact: Artifact,
        section: dict[str, Any],
        section_name: str,
        agents: dict[str, dict[str, Any]],
        disabled: set[str],
        mcp_references: list[tuple[Path, str, list[Any], str]],
        skill_references: list[tuple[Path, str, list[Any], str]],
    ) -> None:
        for agent_id, specification in section.items():
            if not isinstance(agent_id, str):
                self.add_error(
                    artifact.path,
                    f"{section_name} agent IDs must be strings",
                    key=section_name.split(".")[-1],
                    text=artifact.text,
                )
                continue
            if agent_id in disabled:
                continue
            if not isinstance(specification, dict):
                self.add_error(
                    artifact.path,
                    f"{section_name}.{agent_id} must be a mapping",
                    key=agent_id,
                    text=artifact.text,
                )
                continue
            if agent_id in agents:
                self.add_error(
                    artifact.path,
                    f"agent {agent_id!r} is defined more than once",
                    key=agent_id,
                    text=artifact.text,
                )
            agents[agent_id] = specification
            model = specification.get("model")
            if not isinstance(model, str) or not model:
                self.add_error(
                    artifact.path,
                    f"{section_name}.{agent_id}.model must be a non-empty string",
                    key="model",
                    text=artifact.text,
                )
            self._collect_list_reference(
                artifact,
                specification,
                section_name,
                agent_id,
                "mcps",
                mcp_references,
            )
            self._collect_list_reference(
                artifact,
                specification,
                section_name,
                agent_id,
                "skills",
                skill_references,
            )

    def _collect_list_reference(
        self,
        artifact: Artifact,
        specification: dict[str, Any],
        section_name: str,
        agent_id: str,
        field: str,
        references: list[tuple[Path, str, list[Any], str]],
    ) -> None:
        if field not in specification:
            return
        values = specification[field]
        location = f"{section_name}.{agent_id}.{field}"
        if not isinstance(values, list):
            self.add_error(
                artifact.path,
                f"{location} must be a list",
                key=field,
                text=artifact.text,
            )
            return
        if field == "mcps":
            for index, value in enumerate(values):
                if value == CONTEXT7_MCP and agent_id != CONTEXT7_AGENT:
                    self.add_error(
                        artifact.path,
                        f"{location}[{index}] may grant context7 only to agent {CONTEXT7_AGENT!r}",
                        key=field,
                        text=artifact.text,
                    )
        references.append((artifact.path, location, values, artifact.text))

    def validate_models(
        self,
        artifact: Artifact,
        agents: dict[str, dict[str, Any]],
        profile_data: dict[str, dict[str, Any]],
        model_catalog: set[str],
        selected_profile: str | None,
    ) -> None:
        for agent_id, specification in agents.items():
            model = specification.get("model")
            if isinstance(model, str) and model not in model_catalog:
                self.add_error(
                    artifact.path,
                    f"agents.{agent_id}.model references unknown model {model!r}",
                    key=agent_id,
                    text=artifact.text,
                )
            if selected_profile and selected_profile in profile_data:
                expected = profile_data[selected_profile].get(agent_id)
                if expected != model:
                    self.add_error(
                        artifact.path,
                        f"agents.{agent_id}.model {model!r} does not match profile {selected_profile!r} ({expected!r})",
                        key=agent_id,
                        text=artifact.text,
                    )

    def validate_profiles(
        self,
        profile_artifacts: dict[str, Artifact],
        overview_artifact: Artifact | None,
        configured_agents: set[str],
        model_catalog: set[str],
    ) -> dict[str, dict[str, Any]]:
        profiles: dict[str, dict[str, Any]] = {}
        for profile_name, artifact in profile_artifacts.items():
            data = self.require_mapping(artifact, f"model profile {profile_name!r}")
            if data is None:
                continue
            profiles[profile_name] = data
            self.compare_sets(
                artifact.path,
                f"profile {profile_name!r} agent keys",
                configured_agents,
                data.keys(),
                text=artifact.text,
            )
            for agent_id, model in data.items():
                if (
                    not isinstance(agent_id, str)
                    or not isinstance(model, str)
                    or not model
                ):
                    self.add_error(
                        artifact.path,
                        f"profile {profile_name!r} entries must map agent IDs to model IDs",
                        key=str(agent_id),
                        text=artifact.text,
                    )
                elif model not in model_catalog:
                    self.add_error(
                        artifact.path,
                        f"profile {profile_name!r}.{agent_id} references unknown model {model!r}",
                        key=agent_id,
                        text=artifact.text,
                    )

        self.compare_sets(
            self.root / "profiles" / "models",
            "required model profiles",
            REQUIRED_PROFILES,
            profiles.keys(),
        )

        overview = (
            self.require_mapping(overview_artifact, "agents-overview/data.yaml")
            if overview_artifact
            else {}
        )
        if overview is None:
            overview = {}
        overview_path = (
            overview_artifact.path
            if overview_artifact
            else self.root / "agents-overview" / "data.yaml"
        )
        overview_text = overview_artifact.text if overview_artifact else None
        overview_profiles = overview.get("profiles")
        if not isinstance(overview_profiles, dict):
            self.add_error(
                overview_path,
                "profiles must be a mapping",
                key="profiles",
                text=overview_text,
            )
        else:
            self.compare_sets(
                overview_path,
                "overview profile names",
                profiles.keys(),
                overview_profiles.keys(),
                text=overview_text,
            )
            for profile_name, expected in profiles.items():
                actual = overview_profiles.get(profile_name)
                if actual != expected:
                    self.add_error(
                        overview_path,
                        f"profiles.{profile_name} does not match profiles/models/{profile_name}.yml",
                        key=profile_name,
                        text=overview_text,
                    )
        return profiles

    def validate_source_subagents(
        self,
        configured_agents: set[str],
        server_names: set[str],
        disabled_server_names: set[str],
        source_skill_names: set[str],
        payload_skill_names: set[str] | None,
    ) -> None:
        source_dir = self.root / ".rulesync" / "subagents"
        source_names: set[str] = set()
        source_paths = sorted(source_dir.glob("*.md")) if source_dir.is_dir() else []
        for path in source_paths:
            artifact = self._load_frontmatter(path)
            if artifact is None:
                continue
            metadata = self.require_mapping(artifact, "agent frontmatter")
            if metadata is None:
                continue
            name = metadata.get("name")
            if not isinstance(name, str) or not name:
                self.add_error(
                    path,
                    "agent frontmatter name must be a non-empty string",
                    key="name",
                    text=artifact.text,
                )
                continue
            if name in source_names:
                self.add_error(
                    path,
                    f"duplicate source subagent {name!r}",
                    key="name",
                    text=artifact.text,
                )
            source_names.add(name)
            if path.stem != name:
                self.add_error(
                    path,
                    f"filename does not match agent name {name!r}",
                    key="name",
                    text=artifact.text,
                )
            if name not in configured_agents:
                self.add_error(
                    path,
                    f"source subagent {name!r} is not configured in oh-my-opencode-slim.json",
                    key="name",
                    text=artifact.text,
                )
            for field, values in self.frontmatter_lists(path, artifact, metadata):
                if field == "mcps":
                    self.validate_mcp_references(
                        [(path, f"{name}.mcps", values, artifact.text)],
                        server_names,
                        disabled_server_names,
                    )
                else:
                    self.validate_skill_references(
                        path,
                        f"{name}.skills",
                        values,
                        source_skill_names,
                        payload_skill_names,
                        artifact.text,
                    )

        if self.payload is None:
            return
        generated_dir = self.payload / "agents"
        generated_names: set[str] = set()
        for path in (
            sorted(generated_dir.glob("*.md")) if generated_dir.is_dir() else []
        ):
            artifact = self._load_frontmatter(path)
            if artifact is None:
                continue
            metadata = self.require_mapping(artifact, "generated agent frontmatter")
            if metadata is None:
                continue
            name = metadata.get("name")
            if not isinstance(name, str) or not name:
                self.add_error(
                    path,
                    "generated agent name must be a non-empty string",
                    key="name",
                    text=artifact.text,
                )
                continue
            if name in generated_names:
                self.add_error(
                    path,
                    f"duplicate generated subagent {name!r}",
                    key="name",
                    text=artifact.text,
                )
            generated_names.add(name)
            if path.stem != name:
                self.add_error(
                    path,
                    f"filename does not match agent name {name!r}",
                    key="name",
                    text=artifact.text,
                )
            if name not in configured_agents:
                self.add_error(
                    path,
                    f"generated agent {name!r} is not configured",
                    key="name",
                    text=artifact.text,
                )
            for field, values in self.frontmatter_lists(path, artifact, metadata):
                if field == "mcps":
                    self.validate_mcp_references(
                        [(path, f"{name}.mcps", values, artifact.text)],
                        server_names,
                        disabled_server_names,
                    )
                else:
                    self.validate_skill_references(
                        path,
                        f"{name}.skills",
                        values,
                        source_skill_names,
                        payload_skill_names,
                        artifact.text,
                    )
        if source_names != generated_names:
            self.compare_sets(
                self.payload / "agents",
                "staged agent IDs",
                source_names,
                generated_names,
            )

    def _load_frontmatter(self, path: Path) -> Artifact | None:
        text = self.read_text(path)
        if text is None:
            return None
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            self.add_error(path, "agent file must start with YAML frontmatter", line=1)
            return None
        end = next(
            (index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"),
            None,
        )
        if end is None:
            self.add_error(path, "agent frontmatter is not closed", line=1)
            return None
        frontmatter = "".join(lines[1:end])
        if yaml is None:
            self.add_error(path, "PyYAML is required to parse agent frontmatter")
            return None
        try:
            data = yaml.safe_load(frontmatter)
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            line = mark.line + 2 if mark else None
            self.add_error(path, f"invalid agent frontmatter YAML: {error}", line=line)
            return None
        return Artifact(path, text, data)

    def frontmatter_lists(
        self,
        path: Path,
        artifact: Artifact,
        metadata: dict[str, Any],
    ) -> list[tuple[str, list[Any]]]:
        result = []
        for field in ("mcps", "skills"):
            if field not in metadata:
                continue
            values = metadata[field]
            if not isinstance(values, list):
                self.add_error(
                    path,
                    f"frontmatter {field} must be a list",
                    key=field,
                    text=artifact.text,
                )
                continue
            result.append((field, values))
        return result

    def validate_skill_references(
        self,
        path: Path,
        location: str,
        values: Iterable[Any],
        source_skill_names: set[str],
        payload_skill_names: set[str] | None,
        text: str,
    ) -> None:
        for index, value in enumerate(values):
            if not isinstance(value, str):
                self.add_error(
                    path,
                    f"{location}[{index}] must be a string",
                    key=location.split(".")[-1],
                    text=text,
                )
                continue
            if value in EXTERNAL_SKILL_REFERENCES:
                continue
            if value not in source_skill_names:
                self.add_error(
                    path,
                    f"{location}[{index}] references missing .rulesync/skills/{value}",
                    key=value,
                    text=text,
                )
            if payload_skill_names is not None and value not in payload_skill_names:
                self.add_error(
                    path,
                    f"{location}[{index}] is missing from staged skills/{value}",
                    key=value,
                    text=text,
                )

    def validate_overview(
        self,
        artifact: Artifact,
        configured_agents: set[str],
        reviewer_lanes: list[str],
        server_names: set[str],
        disabled_server_names: set[str],
        reviewer_contract_texts: list[tuple[Path, str]],
    ) -> None:
        overview = self.require_mapping(artifact, "agents-overview/data.yaml")
        if overview is None:
            return
        nodes = overview.get("nodes")
        links = overview.get("links")
        if not isinstance(nodes, list):
            self.add_error(
                artifact.path, "nodes must be a list", key="nodes", text=artifact.text
            )
            return
        if not isinstance(links, list):
            self.add_error(
                artifact.path, "links must be a list", key="links", text=artifact.text
            )
            links = []

        nodes_by_id: dict[str, dict[str, Any]] = {}
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                self.add_error(
                    artifact.path,
                    f"nodes[{index}] must be a mapping",
                    key="nodes",
                    text=artifact.text,
                )
                continue
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id:
                self.add_error(
                    artifact.path,
                    f"nodes[{index}].id must be a non-empty string",
                    key="id",
                    text=artifact.text,
                )
                continue
            if node_id in nodes_by_id:
                self.add_error(
                    artifact.path,
                    f"duplicate overview node ID {node_id!r}",
                    key=node_id,
                    text=artifact.text,
                )
            nodes_by_id[node_id] = node

        agent_node_ids = {
            node_id
            for node_id, node in nodes_by_id.items()
            if node.get("type") == "agent"
        }
        self.compare_sets(
            artifact.path,
            "overview agent node IDs",
            configured_agents,
            agent_node_ids,
            text=artifact.text,
        )

        for node_id, node in nodes_by_id.items():
            if node.get("type") == "mcp":
                label = node.get("label")
                if (
                    isinstance(label, str)
                    and label not in server_names
                    and label not in disabled_server_names
                    and label not in BUILTIN_MCP_REFERENCES
                ):
                    self.add_error(
                        artifact.path,
                        f"overview MCP node {node_id!r} references unknown MCP {label!r}",
                        key=node_id,
                        text=artifact.text,
                    )
            if node.get("type") == "agent":
                access = node.get("mcp_access")
                if isinstance(access, str):
                    access_names = [
                        value.strip() for value in access.split(",") if value.strip()
                    ]
                    for access_name in access_names:
                        if access_name == "context-layer":
                            self.add_error(
                                artifact.path,
                                f"overview agent {node_id!r} uses stale MCP name context-layer; use cortex",
                                key=node_id,
                                text=artifact.text,
                            )
                        elif access_name in disabled_server_names:
                            self.add_error(
                                artifact.path,
                                f"overview agent {node_id!r} references disabled MCP {access_name!r}",
                                key=node_id,
                                text=artifact.text,
                            )
                        elif (
                            access_name not in BUILTIN_MCP_REFERENCES
                            and access_name not in server_names
                            and access_name not in NON_MCP_OVERVIEW_ACCESS
                        ):
                            self.add_error(
                                artifact.path,
                                f"overview agent {node_id!r} references unknown MCP {access_name!r}",
                                key=node_id,
                                text=artifact.text,
                            )
                elif access is not None:
                    self.add_error(
                        artifact.path,
                        f"overview agent {node_id!r}.mcp_access must be a string",
                        key=node_id,
                        text=artifact.text,
                    )

        seen_links: set[tuple[str, str, str]] = set()
        for index, link in enumerate(links):
            if not isinstance(link, dict):
                self.add_error(
                    artifact.path,
                    f"links[{index}] must be a mapping",
                    key="links",
                    text=artifact.text,
                )
                continue
            source = link.get("source")
            target = link.get("target")
            label = link.get("label", "")
            invalid_endpoint = False
            for endpoint_name, endpoint in (("source", source), ("target", target)):
                if not isinstance(endpoint, str) or not endpoint:
                    self.add_error(
                        artifact.path,
                        f"links[{index}].{endpoint_name} must be a non-empty string",
                        key="links",
                        text=artifact.text,
                    )
                    invalid_endpoint = True
            if invalid_endpoint:
                continue
            if source not in nodes_by_id or target not in nodes_by_id:
                self.add_error(
                    artifact.path,
                    f"links[{index}] references an unknown node ({source!r} → {target!r})",
                    key="links",
                    text=artifact.text,
                )
                continue
            link_key = (source, target, label if isinstance(label, str) else str(label))
            if link_key in seen_links:
                self.add_error(
                    artifact.path,
                    f"duplicate overview link {source!r} → {target!r}",
                    key="links",
                    text=artifact.text,
                )
            seen_links.add(link_key)

        reviewer = nodes_by_id.get("reviewer")
        if not isinstance(reviewer, dict) or reviewer.get("type") != "agent":
            self.add_error(
                artifact.path,
                "overview reviewer agent node is missing",
                key="reviewer",
                text=artifact.text,
            )
        else:
            dispatches = reviewer.get("dispatches")
            if not isinstance(dispatches, list):
                self.add_error(
                    artifact.path,
                    "overview reviewer.dispatches must be a list",
                    key="dispatches",
                    text=artifact.text,
                )
            else:
                self.compare_sets(
                    artifact.path,
                    "overview reviewer dispatches",
                    reviewer_lanes,
                    dispatches,
                    text=artifact.text,
                )

        overview_lane_nodes = {
            node_id
            for node_id, node in nodes_by_id.items()
            if node.get("type") == "agent" and node_id.startswith(REVIEWER_PREFIX)
        }
        self.compare_sets(
            artifact.path,
            "overview reviewer lane node IDs",
            reviewer_lanes,
            overview_lane_nodes,
            text=artifact.text,
        )

        reviewer_links = set()
        for link in links:
            if not isinstance(link, dict) or link.get("source") != "reviewer":
                continue
            target = link.get("target")
            if isinstance(target, str) and target.startswith(REVIEWER_PREFIX):
                reviewer_links.add(target)
        self.compare_sets(
            artifact.path,
            "overview reviewer link targets",
            reviewer_lanes,
            reviewer_links,
            text=artifact.text,
        )

        for lane in reviewer_lanes:
            node = nodes_by_id.get(lane)
            if isinstance(node, dict) and node.get("parent") != "reviewer":
                self.add_error(
                    artifact.path,
                    f"overview reviewer lane {lane!r} must have parent reviewer",
                    key=lane,
                    text=artifact.text,
                )

        self.validate_reviewer_contracts(reviewer_lanes, reviewer_contract_texts)

    def validate_reviewer_contracts(
        self,
        reviewer_lanes: list[str],
        contract_texts: list[tuple[Path, str]],
    ) -> None:
        expected = set(reviewer_lanes)
        for path, text in contract_texts:
            references = set(re.findall(r"\breviewer-[a-z0-9][a-z0-9-]*\b", text))
            self.compare_sets(
                path,
                "reviewer contract lane references",
                expected,
                references,
                text=text,
            )
            for stale in sorted(references - expected):
                self.add_error(
                    path,
                    f"reviewer contract references unknown lane {stale!r}",
                    key=stale,
                    text=text,
                )

    def validate_reviewer_lane_prompts(
        self,
        artifact: Artifact,
        reviewer_lanes: list[str],
        agents: dict[str, dict[str, Any]],
    ) -> None:
        expected = set(reviewer_lanes)
        reviewer = agents.get("reviewer")
        if reviewer:
            prompt = reviewer.get("prompt")
            if not isinstance(prompt, str):
                self.add_error(
                    artifact.path,
                    "agents.reviewer.prompt must be a string",
                    key="reviewer",
                    text=artifact.text,
                )
            else:
                references = set(re.findall(r"\breviewer-[a-z0-9][a-z0-9-]*\b", prompt))
                self.compare_sets(
                    artifact.path,
                    "runtime reviewer prompt lane references",
                    expected,
                    references,
                    text=artifact.text,
                )
                if (
                    "sequential Phase B" not in prompt
                    or "reviewer-simplifier" not in prompt
                ):
                    self.add_error(
                        artifact.path,
                        "runtime reviewer prompt must describe the sequential reviewer-simplifier Phase B",
                        key="reviewer",
                        text=artifact.text,
                    )

        for lane in reviewer_lanes:
            specification = agents.get(lane)
            if specification is None:
                continue
            prompt = specification.get("prompt")
            if not isinstance(prompt, str):
                self.add_error(
                    artifact.path,
                    f"agents.{lane}.prompt must be a string",
                    key=lane,
                    text=artifact.text,
                )
                continue
            if not _has_reviewer_contract_agent(prompt, lane):
                self.add_error(
                    artifact.path,
                    f"agents.{lane}.prompt must identify the common reviewer contract agent",
                    key=lane,
                    text=artifact.text,
                )
            missing_fields = [
                field for field in REVIEWER_CONTRACT_FIELDS if field not in prompt
            ]
            if missing_fields:
                self.add_error(
                    artifact.path,
                    f"agents.{lane}.prompt is missing reviewer contract fields: {', '.join(missing_fields)}",
                    key=lane,
                    text=artifact.text,
                )

    def validate_skill_references_from_omo(
        self,
        references: list[tuple[Path, str, list[Any], str]],
        source_skill_names: set[str],
        payload_skill_names: set[str] | None,
    ) -> None:
        for path, location, values, text in references:
            self.validate_skill_references(
                path, location, values, source_skill_names, payload_skill_names, text
            )

    def run(self, profile_name: str | None) -> None:
        mcp_artifact = self.load_json(self.root / ".rulesync" / "mcp.jsonc", jsonc=True)
        server_names, disabled_server_names = self.validate_mcp_names(mcp_artifact)
        self.validate_context7_mcp(mcp_artifact)
        self.validate_context7_rule()

        omo_path = (
            self.payload / "oh-my-opencode-slim.json"
            if self.payload
            else self.root / "oh-my-opencode-slim.json"
        )
        omo_artifact = self.load_json(omo_path)
        if omo_artifact is None:
            return
        agents, omo_mcp_refs, omo_skill_refs = self.collect_omo_agents(omo_artifact)
        self.validate_mcp_references(omo_mcp_refs, server_names, disabled_server_names)

        source_skill_dir = self.root / ".rulesync" / "skills"
        source_skill_names = (
            {path.name for path in source_skill_dir.iterdir() if path.is_dir()}
            if source_skill_dir.is_dir()
            else set()
        )
        payload_skill_dir = self.payload / "skills" if self.payload else None
        payload_skill_names = (
            {path.name for path in payload_skill_dir.iterdir() if path.is_dir()}
            if payload_skill_dir and payload_skill_dir.is_dir()
            else set()
            if payload_skill_dir
            else None
        )
        self.validate_skill_references_from_omo(
            omo_skill_refs, source_skill_names, payload_skill_names
        )

        opencode_path = (
            self.payload / "opencode.json"
            if self.payload
            else self.root / "opencode.json"
        )
        opencode_artifact = self.load_json(opencode_path)
        model_catalog = self.model_catalog(opencode_artifact)

        opencode_jsonc_artifact = (
            self.load_json(self.payload / "opencode.jsonc", jsonc=True)
            if self.payload
            else None
        )
        self.validate_opencode_mcp(opencode_jsonc_artifact, mcp_artifact)

        profile_artifacts: dict[str, Artifact] = {}
        profiles_dir = self.root / "profiles" / "models"
        for path in sorted((*profiles_dir.glob("*.yml"), *profiles_dir.glob("*.yaml"))):
            artifact = self.load_yaml(path)
            if artifact is not None:
                profile_artifacts[path.stem] = artifact

        overview_path = self.root / "agents-overview" / "data.yaml"
        overview_artifact = self.load_yaml(overview_path)
        profiles = self.validate_profiles(
            profile_artifacts, overview_artifact, set(agents), model_catalog
        )

        selected_profile = profile_name
        if selected_profile is None and self.payload is None:
            selected_profile = "default"
        if selected_profile and selected_profile not in profiles:
            self.add_error(
                self.root / "profiles" / "models",
                f"selected model profile {selected_profile!r} is not available",
            )
        self.validate_models(
            omo_artifact, agents, profiles, model_catalog, selected_profile
        )

        reviewer_lanes = sorted(
            agent_id for agent_id in agents if agent_id.startswith(REVIEWER_PREFIX)
        )
        reviewer_contracts = []
        reviewer_skill_path = (
            self.root / ".rulesync" / "skills" / "reviewer" / "SKILL.md"
        )
        reviewer_skill_text = self.read_text(reviewer_skill_path)
        if reviewer_skill_text is not None:
            reviewer_contracts.append((reviewer_skill_path, reviewer_skill_text))
        if self.payload:
            staged_reviewer_skill_path = (
                self.payload / "skills" / "reviewer" / "SKILL.md"
            )
            staged_reviewer_skill_text = self.read_text(staged_reviewer_skill_path)
            if staged_reviewer_skill_text is not None:
                reviewer_contracts.append(
                    (staged_reviewer_skill_path, staged_reviewer_skill_text)
                )
        if isinstance(overview_artifact, Artifact):
            self.validate_overview(
                overview_artifact,
                set(agents),
                reviewer_lanes,
                server_names,
                disabled_server_names,
                reviewer_contracts,
            )
        else:
            # Contract validation is independent of the overview YAML. In
            # particular, a staged reviewer skill must still be checked when
            # the overview itself cannot be parsed.
            self.validate_reviewer_contracts(reviewer_lanes, reviewer_contracts)
        self.validate_reviewer_lane_prompts(omo_artifact, reviewer_lanes, agents)

        self.validate_source_subagents(
            set(agents),
            server_names,
            disabled_server_names,
            source_skill_names,
            payload_skill_names,
        )

    def model_catalog(self, artifact: Artifact | None) -> set[str]:
        if artifact is None:
            return set()
        config = self.require_mapping(artifact, "opencode.json")
        if config is None:
            return set()
        providers = config.get("provider")
        if not isinstance(providers, dict):
            self.add_error(
                artifact.path,
                "provider must be a mapping",
                key="provider",
                text=artifact.text,
            )
            return set()
        models: set[str] = set()
        for provider_id, provider in providers.items():
            if not isinstance(provider, dict):
                self.add_error(
                    artifact.path,
                    f"provider.{provider_id} must be a mapping",
                    key=str(provider_id),
                    text=artifact.text,
                )
                continue
            provider_models = provider.get("models")
            if not isinstance(provider_models, dict):
                self.add_error(
                    artifact.path,
                    f"provider.{provider_id}.models must be a mapping",
                    key=str(provider_id),
                    text=artifact.text,
                )
                continue
            models.update(
                f"{provider_id}/{model_id}"
                for model_id in provider_models
                if isinstance(provider_id, str) and isinstance(model_id, str)
            )
        return models

    def validate_opencode_mcp(
        self,
        artifact: Artifact | None,
        source_mcp_artifact: Artifact | None,
    ) -> None:
        if artifact is None or source_mcp_artifact is None:
            return
        config = self.require_mapping(artifact, "opencode.jsonc")
        source = self.require_mapping(source_mcp_artifact, "mcp.jsonc")
        if config is None or source is None:
            return

        source_servers = source.get("mcpServers")
        if not isinstance(source_servers, dict):
            return
        expected = {
            name
            for name, specification in source_servers.items()
            if isinstance(name, str)
            and isinstance(specification, dict)
            and specification.get("enabled", True) is not False
        }
        # `cortex` is the canonical name even when an incomplete or stale
        # source configuration would otherwise omit it. Built-in MCPs are
        # runtime exceptions, not generated server keys that require a source
        # declaration.
        expected.difference_update(BUILTIN_MCP_REFERENCES, {"context-layer"})
        expected.add(CANONICAL_MCP)

        mcp = config.get("mcp")
        if not isinstance(mcp, dict):
            self.add_error(
                artifact.path,
                "mcp must be a mapping",
                key="mcp",
                text=artifact.text,
            )
            return

        actual: set[str] = set()
        for name in mcp:
            if not isinstance(name, str):
                self.add_error(
                    artifact.path,
                    "opencode.jsonc MCP keys must be strings",
                    key="mcp",
                    text=artifact.text,
                )
                continue
            actual.add(name)
            if name == "context-layer":
                self.add_error(
                    artifact.path,
                    "staged opencode.jsonc uses stale MCP name context-layer; use cortex",
                    key=name,
                    text=artifact.text,
                )

        self.compare_sets(
            artifact.path,
            "staged opencode.jsonc MCP keys",
            expected,
            actual - BUILTIN_MCP_REFERENCES - {"context-layer"},
            text=artifact.text,
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repository root (defaults to the parent of this script)",
    )
    parser.add_argument(
        "--payload",
        type=Path,
        default=None,
        help="staged deployment payload to validate against the repository source",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="profile applied to a staged payload (used to verify its effective model assignments)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    validator = Validator(root, args.payload)
    validator.run(args.profile)
    if validator.errors:
        for error in validator.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            f"ai-rules validation failed ({len(validator.errors)} error(s))",
            file=sys.stderr,
        )
        return 1
    print("ai-rules validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
