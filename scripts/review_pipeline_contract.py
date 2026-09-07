"""Pure, deterministic contracts for the declarative review pipeline."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY_PATH = Path(__file__).parents[1] / ".rulesync/skills/review-pipeline/pipeline.json"
_REQUIRED_REGISTRY_FIELDS = (
    "manager",
    "skill",
    "contract_version",
    "max_phase_a_concurrency",
    "aspect_ids",
    "policy",
    "phases",
    "lanes",
    "required_packet_fields",
    "required_lane_result_fields",
    "finding_fields",
    "verdict_precedence",
)
_REQUIRED_LANE_FIELDS = (
    "id",
    "aspect",
    "phase",
    "order",
    "trigger",
    "model_profile_key",
    "required_output_fields",
)
_FINDING_ARRAY_FIELDS = ("critical", "important", "suggestions")
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
    if registry.get("contract_version") != 1:
        errors.append("registry contract_version must be 1")
    max_concurrency = registry.get("max_phase_a_concurrency")
    if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
        errors.append("registry max_phase_a_concurrency must be an integer from 1 to 3")
    elif not 1 <= max_concurrency <= 3:
        errors.append("registry max_phase_a_concurrency must be an integer from 1 to 3")
    aspects = registry.get("aspect_ids")
    if not isinstance(aspects, list) or not aspects or any(not isinstance(aspect, str) or not aspect for aspect in aspects):
        errors.append("registry aspect_ids must be a non-empty string array")
    elif len(set(aspects)) != len(aspects):
        errors.append("registry aspect_ids must be unique")
    policy = registry.get("policy")
    if not isinstance(policy, dict) or not isinstance(policy.get("target_defaults"), dict):
        errors.append("registry policy.target_defaults must be an object")
    elif not policy["target_defaults"]:
        errors.append("registry policy.target_defaults must not be empty")
    phases = registry.get("phases")
    if not isinstance(phases, dict) or not phases or any(
        not isinstance(phase, str) or not isinstance(lanes, list) or not lanes
        or any(not isinstance(lane, str) or not lane for lane in lanes)
        for phase, lanes in (phases.items() if isinstance(phases, dict) else [])
    ):
        errors.append("registry phases must map non-empty names to lane arrays")
    lanes = registry.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append("registry lanes must be a non-empty array")
    else:
        lane_ids: list[str] = []
        for index, lane in enumerate(lanes):
            if not isinstance(lane, dict):
                errors.append(f"registry lane {index} must be an object")
                continue
            lane_id = lane.get("id")
            lane_ids.append(lane_id if isinstance(lane_id, str) else f"<invalid:{index}>")
            for field in _REQUIRED_LANE_FIELDS:
                if field not in lane:
                    errors.append(f"registry lane {lane.get('id', index)} missing field: {field}")
            if not isinstance(lane.get("id"), str) or not lane.get("id"):
                errors.append(f"registry lane {index} id must be a non-empty string")
            if not isinstance(aspects, list) or not isinstance(lane.get("aspect"), str) or lane.get("aspect") not in aspects:
                errors.append(f"registry lane {lane.get('id', index)} has invalid aspect")
            if not isinstance(lane.get("phase"), str) or not isinstance(lane.get("order"), int) or isinstance(lane.get("order"), bool):
                errors.append(f"registry lane {lane.get('id', index)} has invalid phase or order")
            trigger = lane.get("trigger")
            if not isinstance(trigger, str) or not trigger.strip():
                errors.append(f"registry lane {lane.get('id', index)} trigger must be non-empty")
            if not isinstance(lane.get("required_output_fields"), list):
                errors.append(f"registry lane {lane.get('id', index)} required_output_fields must be an array")
        if len(set(lane_ids)) != len(lane_ids):
            errors.append("registry lane ids must be unique")
        if isinstance(phases, dict):
            phase_lane_ids = [lane_id for phase_lanes in phases.values() for lane_id in phase_lanes] if all(
                isinstance(phase_lanes, list) for phase_lanes in phases.values()
            ) else []
            if set(phase_lane_ids) != set(lane_ids) or len(phase_lane_ids) != len(lane_ids):
                errors.append("registry phases must contain every lane exactly once")
    if not isinstance(registry.get("required_packet_fields"), list) or not registry["required_packet_fields"]:
        errors.append("registry required_packet_fields must be a non-empty array")
    if not isinstance(registry.get("required_lane_result_fields"), list) or not registry["required_lane_result_fields"]:
        errors.append("registry required_lane_result_fields must be a non-empty array")
    return errors


def load_registry(path: str | Path) -> dict[str, Any]:
    """Load and validate the canonical review registry without side effects."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError):
        raise ValueError("unable to read review registry") from None
    try:
        registry = json.loads(raw)
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
        raise ValueError("target kind must be a string")
    normalized = target_kind.strip().lower().replace("_", "-").replace(" ", "-")
    policy = registry.get("policy", {})
    aliases = policy.get("target_aliases", {}) if isinstance(policy, dict) else {}
    if not isinstance(aliases, dict):
        aliases = {}
    normalized = aliases.get(normalized, normalized)
    target_defaults = policy.get("target_defaults", {}) if isinstance(policy, dict) else {}
    if normalized not in target_defaults:
        raise ValueError(f"unknown target kind: {normalized}")
    return normalized


def normalize_policy(request: Any, target_kind: str, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize a policy request to one canonical tagged request."""
    active_registry = _get_registry(registry)
    target = _canonical_target_kind(target_kind, active_registry)
    if request is None:
        kind = active_registry["policy"]["target_defaults"][target]
        if kind not in {"auto", "full"}:
            raise ValueError("target default must be auto or full")
        return {"policy": {"kind": kind}}
    if isinstance(request, str):
        textual_aliases = active_registry.get("policy", {}).get("textual_aliases", {})
        alias = textual_aliases.get(request) if isinstance(textual_aliases, dict) else None
        if isinstance(alias, dict):
            return {"policy": copy.deepcopy(alias)}
        raise ValueError("unknown textual policy alias")
    if not isinstance(request, dict) or set(request) != {"policy"}:
        raise ValueError("policy request must contain exactly policy")
    policy = request["policy"]
    if not isinstance(policy, dict) or "kind" not in policy:
        raise ValueError("policy must contain kind")
    kind = policy["kind"]
    if not isinstance(kind, str) or kind not in {"auto", "full", "aspects"}:
        raise ValueError("policy kind must be auto, full, or aspects")
    if kind in {"auto", "full"}:
        if set(policy) != {"kind"}:
            raise ValueError(f"{kind} policy must contain exactly kind")
        return {"policy": {"kind": kind}}
    if set(policy) != {"kind", "values"}:
        raise ValueError("aspects policy must contain exactly kind and values")
    values = policy["values"]
    if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
        raise ValueError("aspect values must be a non-empty string array")
    if len(set(values)) != len(values):
        raise ValueError("aspect values must be unique")
    unknown = [value for value in values if value not in active_registry["aspect_ids"]]
    if unknown:
        raise ValueError(f"unknown aspect: {unknown[0]}")
    return {"policy": {"kind": "aspects", "values": list(values)}}


def resolve_concurrency(raw_value: Any, registry: dict[str, Any] | None = None) -> int:
    """Resolve REVIEWER_MAX_PARALLEL using the documented fail-safe rules."""
    active_registry = _get_registry(registry)
    cap = active_registry["max_phase_a_concurrency"]
    if isinstance(raw_value, int) and not isinstance(raw_value, bool):
        value = raw_value
    elif isinstance(raw_value, str) and raw_value.strip() and _INTEGER.fullmatch(raw_value.strip()):
        value = int(raw_value.strip(), 10)
    else:
        return cap
    if value <= 0:
        return cap
    return min(value, cap)


def _target_from_packet(target: Any) -> str:
    if isinstance(target, str):
        return target
    if isinstance(target, dict):
        return target.get("kind") or target.get("type") or "current-diff"
    return "current-diff"


def validate_packet(packet: Any, registry: dict[str, Any]) -> dict[str, Any]:
    """Validate the complete coordinator packet and return deterministic errors."""
    errors: list[str] = []
    if not isinstance(packet, dict):
        return {"valid": False, "errors": ["packet must be an object"]}
    required = registry.get("required_packet_fields", []) if isinstance(registry, dict) else []
    for field in required:
        if field not in packet:
            errors.append(f"missing packet field: {field}")
    for field in ("target", "scope", "implementer_report", "plan_context", "guidelines"):
        if field in packet and not _is_non_empty(packet[field]):
            errors.append(f"packet field must be non-empty: {field}")
    changed_paths = packet.get("changed_paths")
    if "changed_paths" in packet and (
        not isinstance(changed_paths, list) or any(not isinstance(path, str) or not path for path in changed_paths)
    ):
        errors.append("changed_paths must be an array of non-empty strings")
    if isinstance(changed_paths, list) and len(set(changed_paths)) != len(changed_paths):
        errors.append("changed_paths must be unique")
    diff = packet.get("diff")
    complete_diff = isinstance(diff, dict) and diff.get("complete") is True and any(
        _is_non_empty(diff.get(key)) for key in ("content", "text", "patch")
    )
    if not complete_diff:
        errors.append("diff must be complete and contain content")
    metadata = packet.get("diff_metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("status"), str) or not metadata["status"].strip():
        errors.append("diff_metadata.status is required")
    if "policy" in packet:
        try:
            normalized = normalize_policy(packet["policy"], _target_from_packet(packet.get("target")), registry)
            if normalized != packet["policy"]:
                errors.append("policy is not normalized")
        except ValueError as error:
            errors.append(f"invalid policy: {error}")
    for field in ("review_run_id", "packet_digest"):
        if field in packet and (not isinstance(packet[field], str) or not packet[field].strip()):
            errors.append(f"{field} must be a non-empty string")
    version = packet.get("contract_version")
    if not _is_integer(version) or version != registry.get("contract_version"):
        errors.append("contract_version does not match registry")
    return {"valid": not errors, "errors": errors}


def _expected_run_parts(expected_run: Any) -> tuple[Any, Any, Any, Any, Any, bool]:
    if isinstance(expected_run, str):
        return expected_run, None, None, None, None, False
    if isinstance(expected_run, dict):
        return (
            expected_run.get("review_run_id", expected_run.get("run_id")),
            expected_run.get("packet_digest"),
            expected_run.get("contract_version"),
            expected_run.get("lane", expected_run.get("lane_id", expected_run.get("agent"))),
            expected_run.get("phase"),
            bool(expected_run.get("finalized", False)),
        )
    return None, None, None, None, None, False


def _finding_evidence(finding: dict[str, Any]) -> tuple[Any, Any]:
    evidence = finding.get("evidence")
    if isinstance(evidence, dict):
        return finding.get("side", evidence.get("side")), finding.get("hunk", evidence.get("hunk"))
    return finding.get("side"), finding.get("hunk")


def validate_lane_result(
    result: Any,
    changed_paths: list[str],
    expected_run: Any,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one strict lane result and preserve source-lane attribution."""
    active_registry = _get_registry(registry)
    errors: list[str] = []
    findings: list[dict[str, Any]] = []
    if not isinstance(result, dict):
        return {"valid": False, "errors": ["lane result must be an object"], "findings": []}
    expected_id, expected_digest, expected_version, expected_lane, expected_phase, expected_finalized = _expected_run_parts(expected_run)
    agent = result.get("agent")
    lane_definitions = {
        lane.get("id"): lane for lane in active_registry.get("lanes", []) if isinstance(lane, dict)
    }
    phase_lanes = active_registry.get("phases", {})
    valid_phases = set(phase_lanes) if isinstance(phase_lanes, dict) else set()
    lane_definition = lane_definitions.get(agent)
    if lane_definition is None:
        errors.append("unknown lane agent")
    if expected_id is None or result.get("review_run_id") != expected_id:
        errors.append("review_run_id does not match expected run")
    if expected_digest is None or result.get("packet_digest") != expected_digest:
        errors.append("packet_digest does not match expected run")
    if expected_version is None or result.get("contract_version") != expected_version:
        errors.append("contract_version does not match expected run")
    if expected_lane is not None and agent != expected_lane:
        errors.append("lane result crosses expected lane")
    phase = result.get("phase")
    if phase not in valid_phases:
        errors.append("phase must be A or B")
    elif lane_definition is None or lane_definition.get("phase") != phase or agent not in phase_lanes.get(phase, []):
        errors.append("lane agent is not a member of its phase")
    if expected_phase is not None and phase != expected_phase:
        errors.append("phase does not match expected run")
    if expected_finalized or result.get("finalized") is True:
        errors.append("late result after finalization")
    required_fields = active_registry.get("required_lane_result_fields", [])
    for field in required_fields:
        if field in _FINDING_ARRAY_FIELDS or field in {"agent", "review_run_id", "phase"}:
            continue
        if field == "summary" and (not isinstance(result.get(field), str) or not result[field].strip()):
            errors.append(f"missing or invalid lane field: {field}")
    for field in _FINDING_ARRAY_FIELDS:
        if field in required_fields and not isinstance(result.get(field), list):
            errors.append(f"lane field must be an array: {field}")
    if "positive" in required_fields and not isinstance(result.get("positive"), list):
        errors.append("lane field must be an array: positive")
    if "errors" in required_fields and not isinstance(result.get("errors"), list):
        errors.append("lane field must be an array: errors")
    for severity in _FINDING_ARRAY_FIELDS:
        entries = result.get(severity)
        if not isinstance(entries, list):
            continue
        for index, raw_finding in enumerate(entries):
            reason: str | None = None
            if not isinstance(raw_finding, dict):
                reason = "finding must be an object"
            else:
                file = raw_finding.get("file")
                line = raw_finding.get("line")
                side, hunk = _finding_evidence(raw_finding)
                confidence = raw_finding.get("confidence")
                if not isinstance(file, str) or file not in changed_paths:
                    reason = "finding file must be changed"
                elif not isinstance(line, int) or isinstance(line, bool) or line <= 0:
                    reason = "finding line must be a positive integer"
                elif not isinstance(side, str) or not side.strip() or not isinstance(hunk, str) or not hunk.strip():
                    reason = "finding requires changed-side and hunk evidence"
                elif not isinstance(raw_finding.get("issue"), str) or not raw_finding["issue"].strip():
                    reason = "finding issue must be non-empty"
                elif not isinstance(confidence, int) or isinstance(confidence, bool) or not 0 <= confidence <= 100:
                    reason = "finding confidence must be an integer from 0 to 100"
                elif not isinstance(raw_finding.get("fix"), str) or not raw_finding["fix"].strip():
                    reason = "finding fix must be non-empty"
            if reason:
                errors.append(f"{severity}[{index}]: {reason}")
                continue
            normalized = copy.deepcopy(raw_finding)
            normalized["severity"] = severity
            normalized["source_lane"] = agent
            findings.append(normalized)
    if isinstance(result.get("errors"), list) and result["errors"]:
        errors.append("lane errors array must be empty")
    return {
        "valid": not errors,
        "errors": errors,
        "findings": findings,
        "source_lane": agent,
        "review_run_id": result.get("review_run_id"),
        "phase": phase,
    }


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate equivalent findings while retaining all source lanes."""
    if not isinstance(findings, list):
        raise ValueError("findings must be an array")
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    source_lanes: dict[tuple[Any, ...], set[str]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("finding must be an object")
        issue = finding.get("issue")
        if not isinstance(issue, str):
            raise ValueError("finding issue must be a string")
        key = (
            finding.get("file"),
            finding.get("line"),
            finding.get("severity"),
            " ".join(issue.split()).casefold(),
        )
        lane = finding.get("source_lane", finding.get("agent"))
        if key not in unique:
            unique[key] = copy.deepcopy(finding)
            source_lanes[key] = set()
        if isinstance(lane, str) and lane:
            source_lanes[key].add(lane)
        current = unique[key]
        if finding.get("confidence", -1) > current.get("confidence", -1):
            replacement = copy.deepcopy(finding)
            unique[key] = replacement
    output: list[dict[str, Any]] = []
    for key, finding in unique.items():
        lanes = source_lanes[key]
        if lanes:
            finding["source_lanes"] = sorted(lanes)
            finding["source_lane"] = sorted(lanes)[0]
        output.append(finding)
    return output


def compute_verdict(health: Any, findings: list[dict[str, Any]]) -> str:
    """Compute the health-first deterministic review verdict."""
    healthy = False
    if isinstance(health, bool):
        healthy = health
    elif isinstance(health, str):
        healthy = health.strip().casefold() == "healthy"
    elif isinstance(health, dict):
        if isinstance(health.get("healthy"), bool):
            healthy = health["healthy"]
        elif isinstance(health.get("status"), str):
            healthy = health["status"].strip().casefold() == "healthy"
    if not healthy:
        return "inconclusive"
    if not isinstance(findings, list):
        raise ValueError("findings must be an array")
    severities = set()
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("severity"), str):
            raise ValueError("finding severity is required")
        severity = finding["severity"].casefold()
        if severity not in {"critical", "important", "suggestions"}:
            raise ValueError("finding severity is invalid")
        severities.add(severity)
    if "critical" in severities:
        return "blocked"
    if "important" in severities:
        return "changes-requested"
    if "suggestions" in severities:
        return "approved-with-suggestions"
    return "approved"


__all__ = [
    "compute_verdict",
    "deduplicate_findings",
    "load_registry",
    "normalize_policy",
    "resolve_concurrency",
    "validate_lane_result",
    "validate_packet",
]
