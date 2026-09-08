"""Pure, deterministic contracts for the declarative review pipeline v2."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_PATH = Path(__file__).parents[1] / ".rulesync/skills/review-pipeline/pipeline.json"
_REQUIRED_REGISTRY_FIELDS = ("manager", "skill", "contract_version", "max_concurrency", "focus_ids", "policy", "focuses", "required_packet_fields", "required_result_fields", "finding_fields", "verdict_precedence")
_RESULT_ARRAY_FIELDS = ("critical", "important", "suggestions")
_INTEGER = re.compile(r"^[+-]?\d+$")


def _is_non_empty(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _registry_errors(registry: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(registry, dict):
        return ["registry must be an object"]
    for field in _REQUIRED_REGISTRY_FIELDS:
        if field not in registry:
            errors.append(f"missing registry field: {field}")
    if registry.get("manager") != "orchestrator":
        errors.append("registry manager must be orchestrator")
    if registry.get("skill") != "review-pipeline":
        errors.append("registry skill must be review-pipeline")
    if registry.get("contract_version") != 2:
        errors.append("registry contract_version must be 2")
    cap = registry.get("max_concurrency")
    if not isinstance(cap, int) or isinstance(cap, bool) or not 1 <= cap <= 3:
        errors.append("registry max_concurrency must be an integer from 1 to 3")
    focus_ids = registry.get("focus_ids")
    if not isinstance(focus_ids, list) or not focus_ids or any(not isinstance(focus, str) or not focus for focus in focus_ids):
        errors.append("registry focus_ids must be a non-empty string array")
        focus_ids = []
    elif len(set(focus_ids)) != len(focus_ids):
        errors.append("registry focus_ids must be unique")
    focuses = registry.get("focuses")
    if not isinstance(focuses, list) or not focuses:
        errors.append("registry focuses must be a non-empty array")
        focuses = []
    focus_definitions: list[str] = []
    for index, focus in enumerate(focuses):
        if not isinstance(focus, dict):
            errors.append(f"registry focus {index} must be an object")
            continue
        focus_id = focus.get("id")
        focus_definitions.append(focus_id if isinstance(focus_id, str) else f"<invalid:{index}>")
        for field in ("id", "trigger", "focus_instruction", "required_output_fields", "target"):
            if field not in focus:
                errors.append(f"registry focus {focus.get('id', index)} missing field: {field}")
        if not isinstance(focus_id, str) or not focus_id:
            errors.append(f"registry focus {index} id must be a non-empty string")
        if not isinstance(focus.get("trigger"), str) or not focus["trigger"].strip():
            errors.append(f"registry focus {focus.get('id', index)} trigger must be non-empty")
        if not isinstance(focus.get("focus_instruction"), str) or not focus["focus_instruction"].strip():
            errors.append(f"registry focus {focus.get('id', index)} focus_instruction must be non-empty")
        if focus.get("target") != "reviewer":
            errors.append(f"registry focus {focus.get('id', index)} target must be reviewer")
        if not isinstance(focus.get("required_output_fields"), list):
            errors.append(f"registry focus {focus.get('id', index)} required_output_fields must be an array")
    if focus_definitions != focus_ids:
        errors.append("registry focuses must match focus_ids in canonical order")
    policy = registry.get("policy")
    if not isinstance(policy, dict) or not all(isinstance(policy.get(field), dict) and policy[field] for field in ("target_aliases", "textual_aliases", "target_defaults")):
        errors.append("registry policy aliases and defaults must be non-empty mappings")
    for field in ("required_packet_fields", "required_result_fields", "finding_fields", "verdict_precedence"):
        if not isinstance(registry.get(field), list) or not registry[field]:
            errors.append(f"registry {field} must be a non-empty array")
    return errors


def load_registry(path: str | Path) -> dict[str, Any]:
    try:
        registry = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError:
        raise ValueError("unable to read review registry") from None
    except json.JSONDecodeError:
        raise ValueError("review registry is not valid JSON") from None
    errors = _registry_errors(registry)
    if errors:
        raise ValueError("; ".join(errors))
    return registry


def _get_registry(registry: dict[str, Any] | None) -> dict[str, Any]:
    return load_registry(DEFAULT_REGISTRY_PATH) if registry is None else registry


def _canonical_target_kind(target_kind: Any, registry: dict[str, Any]) -> str:
    if not isinstance(target_kind, str):
        raise TypeError("target kind must be a string")
    normalized = target_kind.strip().lower().replace("_", "-").replace(" ", "-")
    policy = registry.get("policy", {})
    normalized = policy.get("target_aliases", {}).get(normalized, normalized) if isinstance(policy, dict) else normalized
    if normalized not in policy.get("target_defaults", {}):
        raise ValueError(f"unknown target kind: {normalized}")
    return normalized


def normalize_policy(request: Any, target_kind: str, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    active = _get_registry(registry)
    target = _canonical_target_kind(target_kind, active)
    if request is None:
        kind = active["policy"]["target_defaults"][target]
        if kind not in {"auto", "full"}:
            raise ValueError("target default must be auto or full")
        return {"policy": {"kind": kind}}
    if isinstance(request, str):
        alias = active.get("policy", {}).get("textual_aliases", {}).get(request)
        if isinstance(alias, dict):
            return {"policy": copy.deepcopy(alias)}
        raise ValueError("unknown textual policy alias")
    if not isinstance(request, dict) or set(request) != {"policy"}:
        raise ValueError("policy request must contain exactly policy")
    policy = request["policy"]
    if not isinstance(policy, dict) or "kind" not in policy:
        raise ValueError("policy must contain kind")
    kind = policy["kind"]
    if kind in {"auto", "full"}:
        if set(policy) != {"kind"}:
            raise ValueError(f"{kind} policy must contain exactly kind")
        return {"policy": {"kind": kind}}
    if kind != "aspects" or set(policy) != {"kind", "values"}:
        raise ValueError("policy kind must be auto, full, or aspects")
    values = policy["values"]
    if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
        raise ValueError("aspect values must be a non-empty string array")
    if len(set(values)) != len(values):
        raise ValueError("aspect values must be unique")
    unknown = [value for value in values if value not in active["focus_ids"]]
    if unknown:
        raise ValueError(f"unknown focus: {unknown[0]}")
    return {"policy": {"kind": "aspects", "values": list(values)}}


def resolve_concurrency(raw_value: Any, registry: dict[str, Any] | None = None) -> int:
    active = _get_registry(registry)
    cap = active["max_concurrency"]
    if isinstance(raw_value, int) and not isinstance(raw_value, bool):
        value = raw_value
    elif isinstance(raw_value, str) and raw_value.strip() and _INTEGER.fullmatch(raw_value.strip()):
        value = int(raw_value.strip(), 10)
    else:
        return cap
    return cap if value <= 0 else min(value, cap)


def _target_from_packet(target: Any) -> str:
    if isinstance(target, str):
        return target
    if isinstance(target, dict):
        return target.get("kind") or target.get("type") or "current-diff"
    return "current-diff"


def validate_packet(packet: Any, registry: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return {"valid": False, "errors": ["packet must be an object"]}
    for field in registry.get("required_packet_fields", []):
        if field not in packet:
            errors.append(f"missing packet field: {field}")
    for field in ("target", "scope", "implementer_report", "plan_context", "guidelines"):
        if field in packet and not _is_non_empty(packet[field]):
            errors.append(f"packet field must be non-empty: {field}")
    changed_paths = packet.get("changed_paths")
    if not isinstance(changed_paths, list) or any(not isinstance(path, str) or not path for path in changed_paths):
        errors.append("changed_paths must be an array of non-empty strings")
    elif len(set(changed_paths)) != len(changed_paths):
        errors.append("changed_paths must be unique")
    diff = packet.get("diff")
    if not isinstance(diff, dict) or diff.get("complete") is not True or not any(_is_non_empty(diff.get(key)) for key in ("content", "text", "patch")):
        errors.append("diff must be complete and contain content")
    metadata = packet.get("diff_metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("status"), str) or not metadata["status"].strip():
        errors.append("diff_metadata.status is required")
    if "policy" in packet:
        try:
            if normalize_policy(packet["policy"], _target_from_packet(packet.get("target")), registry) != packet["policy"]:
                errors.append("policy is not normalized")
        except ValueError as error:
            errors.append(f"invalid policy: {error}")
    for field in ("review_run_id", "review_invocation_id", "packet_digest"):
        if field in packet and (not isinstance(packet[field], str) or not packet[field].strip()):
            errors.append(f"{field} must be a non-empty string")
    if not _is_integer(packet.get("contract_version")) or packet.get("contract_version") != registry.get("contract_version"):
        errors.append("contract_version does not match registry")
    return {"valid": not errors, "errors": errors}


def _expected_run_parts(expected_run: Any) -> tuple[Any, Any, Any, Any, Any, Any, bool]:
    if isinstance(expected_run, str):
        return expected_run, None, None, None, None, None, False
    if isinstance(expected_run, dict):
        return (expected_run.get("review_run_id", expected_run.get("run_id")), expected_run.get("review_invocation_id", expected_run.get("invocation_id")), expected_run.get("packet_digest"), expected_run.get("contract_version"), expected_run.get("reviewer", expected_run.get("agent")), expected_run.get("focus"), bool(expected_run.get("finalized", False)))
    return None, None, None, None, None, None, False


def _finding_evidence(finding: dict[str, Any]) -> tuple[Any, Any]:
    evidence = finding.get("evidence")
    if isinstance(evidence, dict):
        return finding.get("side", evidence.get("side")), finding.get("hunk", evidence.get("hunk"))
    return finding.get("side"), finding.get("hunk")


def validate_reviewer_result(result: Any, changed_paths: list[str], expected_run: Any, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    active = _get_registry(registry)
    errors: list[str] = []
    findings: list[dict[str, Any]] = []
    if not isinstance(result, dict):
        return {"valid": False, "errors": ["reviewer result must be an object"], "findings": []}
    expected_run_id, expected_invocation, expected_digest, expected_version, expected_reviewer, expected_focus, finalized = _expected_run_parts(expected_run)
    reviewer = result.get("reviewer")
    focus_ids = set(active.get("focus_ids", []))
    if reviewer != "reviewer":
        errors.append("unknown reviewer identity")
    if expected_run_id is None or result.get("review_run_id") != expected_run_id:
        errors.append("review_run_id does not match expected run")
    if expected_invocation is None or result.get("review_invocation_id") != expected_invocation:
        errors.append("review_invocation_id does not match expected invocation")
    if expected_digest is None or result.get("packet_digest") != expected_digest:
        errors.append("packet_digest does not match expected run")
    if expected_version is None or result.get("contract_version") != expected_version:
        errors.append("contract_version does not match expected run")
    if expected_reviewer is not None and reviewer != expected_reviewer:
        errors.append("reviewer result crosses expected reviewer")
    focus = result.get("focus")
    if focus not in focus_ids:
        errors.append("focus must be declared in the registry")
    if expected_focus is not None and focus != expected_focus:
        errors.append("focus does not match expected invocation")
    if finalized or result.get("finalized") is True:
        errors.append("late result after finalization")
    required = active.get("required_result_fields", [])
    for field in required:
        if field in _RESULT_ARRAY_FIELDS or field in {"reviewer", "review_run_id", "review_invocation_id", "packet_digest", "contract_version", "focus"}:
            continue
        if field == "summary" and (not isinstance(result.get(field), str) or not result[field].strip()):
            errors.append(f"missing or invalid reviewer field: {field}")
    for field in _RESULT_ARRAY_FIELDS:
        if field in required and not isinstance(result.get(field), list):
            errors.append(f"reviewer field must be an array: {field}")
    for field in ("positive", "errors"):
        if field in required and not isinstance(result.get(field), list):
            errors.append(f"reviewer field must be an array: {field}")
    for severity in _RESULT_ARRAY_FIELDS:
        entries = result.get(severity)
        if not isinstance(entries, list):
            continue
        for index, raw in enumerate(entries):
            reason = None
            if not isinstance(raw, dict):
                reason = "finding must be an object"
            else:
                file, line, confidence = raw.get("file"), raw.get("line"), raw.get("confidence")
                side, hunk = _finding_evidence(raw)
                if not isinstance(file, str) or file not in changed_paths:
                    reason = "finding file must be changed"
                elif not isinstance(line, int) or isinstance(line, bool) or line <= 0:
                    reason = "finding line must be a positive integer"
                elif not isinstance(side, str) or not side.strip() or not isinstance(hunk, str) or not hunk.strip():
                    reason = "finding requires changed-side and hunk evidence"
                elif not isinstance(raw.get("issue"), str) or not raw["issue"].strip():
                    reason = "finding issue must be non-empty"
                elif not isinstance(confidence, int) or isinstance(confidence, bool) or not 0 <= confidence <= 100:
                    reason = "finding confidence must be an integer from 0 to 100"
                elif not isinstance(raw.get("fix"), str) or not raw["fix"].strip():
                    reason = "finding fix must be non-empty"
            if reason:
                errors.append(f"{severity}[{index}]: {reason}")
                continue
            normalized = copy.deepcopy(raw)
            normalized.update({"severity": severity, "source_focus": focus, "source_invocation_id": result.get("review_invocation_id")})
            findings.append(normalized)
    if isinstance(result.get("errors"), list) and result["errors"]:
        errors.append("reviewer errors array must be empty")
    return {"valid": not errors, "errors": errors, "findings": findings, "reviewer": reviewer, "review_run_id": result.get("review_run_id"), "review_invocation_id": result.get("review_invocation_id"), "focus": focus}


def validate_lane_result(result: Any, changed_paths: list[str], expected_run: Any, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Backward-compatible function name; results are reviewer/focus based."""
    return validate_reviewer_result(result, changed_paths, expected_run, registry)


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(findings, list):
        raise TypeError("findings must be an array")
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    sources: dict[tuple[Any, ...], set[tuple[Any, Any]]] = {}
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("issue"), str):
            raise TypeError("finding must contain a string issue")
        key = (finding.get("file"), finding.get("line"), finding.get("severity"), " ".join(finding["issue"].split()).casefold())
        unique.setdefault(key, copy.deepcopy(finding))
        source = (finding.get("source_focus"), finding.get("source_invocation_id"))
        if all(isinstance(value, str) and value for value in source):
            sources.setdefault(key, set()).add(source)
        if finding.get("confidence", -1) > unique[key].get("confidence", -1):
            unique[key] = copy.deepcopy(finding)
    output = []
    for key, finding in unique.items():
        if sources.get(key):
            finding["source_focuses"] = sorted({focus for focus, _ in sources[key]})
            finding["source_invocation_ids"] = sorted({invocation for _, invocation in sources[key]})
            finding["source_focus"], finding["source_invocation_id"] = min(sources[key])
        output.append(finding)
    return output


def compute_verdict(health: Any, findings: list[dict[str, Any]]) -> str:
    if isinstance(health, bool):
        healthy = health
    elif isinstance(health, str):
        healthy = health.strip().casefold() == "healthy"
    elif isinstance(health, dict):
        healthy = health.get("healthy") if isinstance(health.get("healthy"), bool) else str(health.get("status", "")).strip().casefold() == "healthy"
    else:
        healthy = False
    if not healthy:
        return "inconclusive"
    if not isinstance(findings, list):
        raise TypeError("findings must be an array")
    severities = {finding.get("severity", "").casefold() for finding in findings if isinstance(finding, dict)}
    if not severities <= {"critical", "important", "suggestions"}:
        raise ValueError("finding severity is invalid")
    if "critical" in severities:
        return "blocked"
    if "important" in severities:
        return "changes-requested"
    if "suggestions" in severities:
        return "approved-with-suggestions"
    return "approved"


__all__ = ["compute_verdict", "deduplicate_findings", "load_registry", "normalize_policy", "resolve_concurrency", "validate_lane_result", "validate_packet", "validate_reviewer_result"]
