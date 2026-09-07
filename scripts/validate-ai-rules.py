#!/usr/bin/env python3
"""Validate the cross-artifact contracts used by the ai-rules deployment.

The validator is deliberately read-only.  It can inspect the tracked source
tree directly, or compare that source tree with a staged deployment payload.
"""

from __future__ import annotations

import argparse
import hashlib
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
SUPPORTED_MCP_TRANSPORTS = frozenset({"local", "http", "sse"})
REVIEWER_COORDINATOR = "reviewer-coordinator"
# Keep this registry in execution order. The first nine lanes are Phase A;
# reviewer-simplifier is the sequential Phase B lane.
REVIEWER_LANES: tuple[str, ...] = (
    "reviewer-code",
    "reviewer-test",
    "reviewer-errors",
    "reviewer-types",
    "reviewer-security",
    "reviewer-performance",
    "reviewer-data-integrity",
    "reviewer-accessibility",
    "reviewer-comments",
    "reviewer-simplifier",
)
REVIEWER_PHASE_A_LANES = REVIEWER_LANES[:-1]
REVIEWER_IDS = (REVIEWER_COORDINATOR, *REVIEWER_LANES)
REVIEWER_ID_PATTERN = re.compile(r"\breviewer-[a-z0-9][a-z0-9-]*\b")
GITNEXUS_EXECUTABLE = "/Users/guilhermebomfim/.local/bin/gitnexus"
GITNEXUS_ENV_EXECUTABLE = "/usr/bin/env"
GITNEXUS_ENV_ASSIGNMENT = "GITNEXUS_MCP_READ_ONLY=1"
GITNEXUS_COMMAND = "mcp"
# Supplied by the user's OpenCode installation, not vendored into this repo.
EXTERNAL_SKILL_REFERENCES = frozenset({"orca-cli"})
AGENT_CONTRACT_FIELDS = (
    "name",
    "description",
    "model",
    "tools",
    "mcps",
    "skills",
    "variant",
    "prompt",
    "orchestratorPrompt",
    "routing",
    "mode",
    "permission",
    "permissions",
)
REQUIRED_GENERATED_AGENT_FIELDS = frozenset({"name", "description"})
AGENT_CONTRACT_FIELD_SHAPES = {
    "name": "non_empty_string",
    "description": "non_empty_string",
    "model": "non_empty_string",
    "tools": "string_list",
    "mcps": "string_list",
    "skills": "string_list",
    "variant": "non_empty_string",
    "prompt": "non_empty_string",
    "orchestratorPrompt": "non_empty_string",
    "routing": "mapping",
    "mode": "non_empty_string",
    "permission": "mapping",
    "permissions": "mapping",
}
EXPECTED_MCP_ASSIGNMENTS = {
    "orchestrator": ("gitnexus", "github"),
    "oracle": ("gitnexus",),
    "explorer": ("gitnexus",),
    "detective": ("gitnexus",),
    "designer": ("figma-mcp",),
    "fixer": (),
    REVIEWER_COORDINATOR: ("gitnexus",),
    **{lane: () for lane in REVIEWER_LANES},
    "sage": ("cortex",),
    "navigator": (),
    "observer": (),
    "librarian": ("websearch", "context7", "gh_grep", "linear", "cortex"),
}
NON_MCP_OVERVIEW_ACCESS = frozenset({"agent-browser CLI", "pup CLI"})
PROFILE_SCHEMA_VERSION = 1
REQUIRED_PROFILES = ("default", "cost-efficient")
REVIEWER_CONTRACT_FIELDS = (
    '"critical"',
    '"important"',
    '"suggestions"',
    '"positive"',
    '"errors"',
)
REVIEWER_HEALTH_FIELDS = (
    "coordinator",
    "concurrency",
    "completed",
    "failed",
    "runtime smoke evidence",
    "effective permission evidence",
    "repository immutability",
    "degraded/inconclusive",
)
FIXER_BATCH_MAX = 3
FIXER_MODEL = "bf-o/gpt-5.6-luna"
UNSUPPORTED_THINKING_PARAMETERS = frozenset({"temperature", "top_p", "top_k"})
BIFROST_CREDENTIAL_REFERENCE = (
    "{file:/Users/guilhermebomfim/.config/gorgias-ai/bifrost-virtual-key}"
)
FIXER_PROVIDER = "bf-o"
FIXER_MODEL_KEY = "gpt-5.6-luna"
FIXER_REASONING_EFFORT = "high"
OPENCODE_MANIFEST_NAME = ".ai-rules.manifest.json"
OPENCODE_MANAGED_BY = "ai-rules/deploy.sh"
OPENCODE_MANIFEST_VERSION = 1
PORTABLE_AGENT_OUTPUT_PATHS = {
    "navigator": "~/.cache/opencode/agent-output/navigator/**",
    "sage": "~/.cache/opencode/agent-output/sage/**",
}
RULESYNC_TARGETS = frozenset({"opencode"})
OPENCODE_OUTPUT_ROOT = str(Path.home())

COORDINATOR_READ_PERMISSION = {
    "*": "deny",
}
COORDINATOR_NATIVE_READ_TOOLS = (
    "read",
    "glob",
    "grep",
    "list",
    "lsp",
    "codesearch",
    "ast_grep_search",
)
COORDINATOR_DENIED_TOOLS = (
    "read",
    "glob",
    "grep",
    "list",
    "lsp",
    "codesearch",
    "ast_grep_search",
    "bash",
    "edit",
    "write",
    "apply_patch",
    "ast_grep_replace",
    "task_cancel",
    "task_message",
    "task_revive",
    "question",
    "external_directory",
)


def _has_reviewer_contract_agent(text: str, lane: str) -> bool:
    """Return whether text contains the lane's JSON contract agent field."""

    return re.search(rf'"agent"\s*:\s*"{re.escape(lane)}"', text) is not None


def _reviewer_shaped_ids(values: Iterable[Any]) -> list[str]:
    """Extract reviewer-shaped IDs without treating them as approved lanes."""

    return [
        value
        for value in values
        if isinstance(value, str)
        and REVIEWER_ID_PATTERN.fullmatch(value)
    ]


def _reviewer_candidates(values: Iterable[Any]) -> list[str]:
    """Extract only values that the OpenCode orchestrator could target as reviewers."""

    return [
        value
        for value in values
        if isinstance(value, str)
        and (value == "reviewer" or value.startswith("reviewer-"))
    ]


def _reviewer_shaped_references(text: str) -> list[str]:
    """Extract every reviewer-shaped reference before registry filtering."""

    return REVIEWER_ID_PATTERN.findall(text)


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
    def __init__(
        self,
        root: Path,
        payload: Path | None,
        opencode_config: Path | None = None,
    ):
        self.root = root.resolve()
        self.payload = payload.resolve() if payload else None
        self.opencode_config = (
            opencode_config.resolve() if opencode_config else None
        )
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
        except (OSError, UnicodeDecodeError) as error:
            self.add_error(path, f"cannot read file as UTF-8: {error}")
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

    def validate_mcp_transports(self, artifact: Artifact | None) -> None:
        """Validate generic MCP transport fields and GitNexus safety wiring."""

        if artifact is None:
            return
        mcp = self.require_mapping(artifact, "mcp.jsonc")
        if mcp is None:
            return
        servers = mcp.get("mcpServers")
        if not isinstance(servers, dict):
            return

        for name, specification in servers.items():
            if not isinstance(specification, dict):
                self.add_error(
                    artifact.path,
                    f"mcpServers.{name} must be a mapping",
                    key=str(name),
                    text=artifact.text,
                )
                continue
            transport = specification.get("type")
            if not isinstance(transport, str) or not transport:
                self.add_error(
                    artifact.path,
                    f"mcpServers.{name}.type must be a non-empty string",
                    key=str(name),
                    text=artifact.text,
                )
                continue
            if transport not in SUPPORTED_MCP_TRANSPORTS:
                self.add_error(
                    artifact.path,
                    f"mcpServers.{name}.type uses unsupported MCP transport {transport!r}",
                    key="type",
                    text=artifact.text,
                )
                continue
            if transport == "local":
                command = specification.get("command")
                if (
                    not isinstance(command, list)
                    or not command
                    or any(not isinstance(argument, str) or not argument for argument in command)
                ):
                    self.add_error(
                        artifact.path,
                        f"mcpServers.{name}.command must be a non-empty argv list of strings for local MCP servers",
                        key="command",
                        text=artifact.text,
                    )
            elif transport in {"http", "sse"}:
                url = specification.get("url")
                if not isinstance(url, str) or not url:
                    self.add_error(
                        artifact.path,
                        f"mcpServers.{name}.url must be a non-empty string for remote MCP servers",
                        key="url",
                        text=artifact.text,
                    )

        gitnexus = servers.get("gitnexus")
        if not isinstance(gitnexus, dict):
            self.add_error(
                artifact.path,
                "mcpServers.gitnexus must be declared as an enabled local server",
                key="gitnexus",
                text=artifact.text,
            )
            return
        if gitnexus.get("enabled") is not True:
            self.add_error(
                artifact.path,
                "mcpServers.gitnexus must be enabled",
                key="gitnexus",
                text=artifact.text,
            )
        if gitnexus.get("type") != "local":
            self.add_error(
                artifact.path,
                "mcpServers.gitnexus must use the local transport",
                key="gitnexus",
                text=artifact.text,
            )
        command = gitnexus.get("command")
        if isinstance(command, list) and all(isinstance(argument, str) for argument in command):
            if len(command) != 4:
                self.add_error(
                    artifact.path,
                    "mcpServers.gitnexus.command must contain exactly env, one read-only assignment, the pinned executable, and mcp",
                    key="command",
                    text=artifact.text,
                )
            else:
                expected_parts = (
                    (0, GITNEXUS_ENV_EXECUTABLE, "must invoke /usr/bin/env"),
                    (1, GITNEXUS_ENV_ASSIGNMENT, "must set exactly GITNEXUS_MCP_READ_ONLY=1"),
                    (2, GITNEXUS_EXECUTABLE, f"must use the pinned executable {GITNEXUS_EXECUTABLE!r}"),
                    (3, GITNEXUS_COMMAND, "must end with the mcp command"),
                )
                for index, expected, message in expected_parts:
                    if command[index] != expected:
                        self.add_error(
                            artifact.path,
                            f"mcpServers.gitnexus.command {message}",
                            key="command",
                            text=artifact.text,
                        )
        environment = gitnexus.get("environment")
        if environment is not None:
            self.add_error(
                artifact.path,
                "mcpServers.gitnexus must encode read-only mode in its command argv, not environment",
                key="environment",
                text=artifact.text,
            )

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

    def validate_mcp_assignments(
        self, artifact: Artifact, agents: dict[str, dict[str, Any]]
    ) -> None:
        """Enforce the approved GitNexus ownership matrix."""

        unexpected_agents = sorted(set(agents) - set(EXPECTED_MCP_ASSIGNMENTS))
        if unexpected_agents:
            self.add_error(
                artifact.path,
                "configured agents are outside the expected MCP assignment allowlist: "
                + ", ".join(unexpected_agents),
                key="agents",
                text=artifact.text,
            )

        for agent_id, expected in EXPECTED_MCP_ASSIGNMENTS.items():
            specification = agents.get(agent_id)
            if not isinstance(specification, dict):
                self.add_error(
                    artifact.path,
                    f"agent {agent_id!r} required by the MCP assignment matrix is missing",
                    key=agent_id,
                    text=artifact.text,
                )
                continue
            if "mcps" not in specification:
                self.add_error(
                    artifact.path,
                    f"agents.{agent_id}.mcps must be present as a list",
                    key=agent_id,
                    text=artifact.text,
                )
                continue
            actual = specification["mcps"]
            if not isinstance(actual, list):
                self.add_error(
                    artifact.path,
                    f"agents.{agent_id}.mcps must be a list",
                    key="mcps",
                    text=artifact.text,
                )
                continue
            actual_names = tuple(actual)
            if actual_names != expected:
                self.add_error(
                    artifact.path,
                    f"agents.{agent_id}.mcps must be exactly {list(expected)!r}, got {list(actual_names)!r}",
                    key="mcps",
                    text=artifact.text,
                )

        assigned_agents = set(EXPECTED_MCP_ASSIGNMENTS)
        for agent_id, specification in agents.items():
            actual = specification.get("mcps", [])
            if not isinstance(actual, list):
                continue
            forbidden = [
                value
                for value in actual
                if value == "gitnexus" and agent_id not in assigned_agents
            ]
            if forbidden:
                self.add_error(
                    artifact.path,
                    f"agents.{agent_id}.mcps grants GitNexus outside the approved assignment matrix: {forbidden!r}",
                    key="mcps",
                    text=artifact.text,
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

    def validate_opencode_reviewer_routing(self, artifact: Artifact) -> None:
        """Validate the OpenCode coordinator ownership boundary."""

        config = self.require_mapping(artifact, "oh-my-opencode-slim.json")
        if config is None:
            return

        presets = config.get("presets")
        active_preset = config.get("preset", "bifrost")
        if not isinstance(presets, dict) or not isinstance(active_preset, str):
            return

        active_preset_specification = presets.get(active_preset)
        if not isinstance(active_preset_specification, dict):
            return

        orchestrator = active_preset_specification.get("orchestrator")
        if not isinstance(orchestrator, dict):
            self.add_error(
                artifact.path,
                f"presets.{active_preset}.orchestrator must be a mapping for reviewer coordinator ownership",
                key="orchestrator",
                text=artifact.text,
            )
        else:
            skills = orchestrator.get("skills")
            if not isinstance(skills, list):
                self.add_error(
                    artifact.path,
                    f"presets.{active_preset}.orchestrator.skills must be a list for reviewer coordinator ownership",
                    key="skills",
                    text=artifact.text,
                )
            elif REVIEWER_COORDINATOR in skills:
                self.add_error(
                    artifact.path,
                    f"presets.{active_preset}.orchestrator.skills must not preload {REVIEWER_COORDINATOR}",
                    key="skills",
                    text=artifact.text,
                )

        custom_agents = config.get("agents")
        if not isinstance(custom_agents, dict):
            self.add_error(
                artifact.path,
                "agents must be a mapping for reviewer coordinator ownership",
                key="agents",
                text=artifact.text,
            )
            return

        disabled_agents = config.get("disabled_agents", [])
        disabled_agents = (
            {value for value in disabled_agents if isinstance(value, str)}
            if isinstance(disabled_agents, list)
            else set()
        )
        if "reviewer" in custom_agents and "reviewer" not in disabled_agents:
            self.add_error(
                artifact.path,
                "agents.reviewer is an active legacy coordinator alias; use reviewer-coordinator",
                key="reviewer",
                text=artifact.text,
            )
        coordinator = custom_agents.get(REVIEWER_COORDINATOR)
        if not isinstance(coordinator, dict):
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR} is required for reviewer ownership",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )

    def validate_agent_output_permissions(self, artifact: Artifact) -> None:
        """Require narrow, host-portable paths for agent-generated output."""

        config = self.require_mapping(artifact, "oh-my-opencode-slim.json")
        if config is None:
            return
        agents = config.get("agents")
        if not isinstance(agents, dict):
            return

        for agent_id, expected_path in PORTABLE_AGENT_OUTPUT_PATHS.items():
            specification = agents.get(agent_id)
            if not isinstance(specification, dict):
                self.add_error(
                    artifact.path,
                    f"agents.{agent_id} must define a portable output permission",
                    key=agent_id,
                    text=artifact.text,
                )
                continue
            permission = specification.get("permission")
            if not isinstance(permission, dict):
                self.add_error(
                    artifact.path,
                    f"agents.{agent_id}.permission must define a portable output permission",
                    key=agent_id,
                    text=artifact.text,
                )
                continue

            for permission_name in ("edit", "write", "external_directory"):
                rules = permission.get(permission_name)
                if not isinstance(rules, dict):
                    self.add_error(
                        artifact.path,
                        f"agents.{agent_id}.permission.{permission_name} must be a mapping",
                        key=permission_name,
                        text=artifact.text,
                    )
                    continue
                if rules.get("*") != "deny" or rules.get(expected_path) != "allow":
                    self.add_error(
                        artifact.path,
                        f"agents.{agent_id}.permission.{permission_name} must deny broadly and allow only {expected_path!r}",
                        key=permission_name,
                        text=artifact.text,
                    )
                allowed_paths = {
                    path for path, action in rules.items() if action == "allow"
                }
                if allowed_paths != {expected_path}:
                    self.add_error(
                        artifact.path,
                        f"agents.{agent_id}.permission.{permission_name} has unexpected allowed paths: {sorted(allowed_paths)}",
                        key=permission_name,
                        text=artifact.text,
                    )

            prompt = specification.get("prompt")
            prompt_path = expected_path.removesuffix("**")
            if not isinstance(prompt, str) or prompt_path not in prompt:
                self.add_error(
                    artifact.path,
                    f"agents.{agent_id}.prompt must document the portable output path {prompt_path!r}",
                    key=agent_id,
                    text=artifact.text,
                )

        for legacy_path in ("/tmp/navigator", "/tmp/sage"):
            if legacy_path in artifact.text:
                self.add_error(
                    artifact.path,
                    f"agent output permissions must not use hardcoded {legacy_path!r}",
                    key=legacy_path,
                    text=artifact.text,
                )

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
                expected_spec = profile_data[selected_profile].get(agent_id)
                if isinstance(expected_spec, dict):
                    expected_model = expected_spec.get("model")
                    if expected_model != model:
                        self.add_error(
                            artifact.path,
                            f"agents.{agent_id}.model {model!r} does not match profile {selected_profile!r} ({expected_model!r})",
                            key=agent_id,
                            text=artifact.text,
                        )
                    # Validate variant preservation
                    expected_variant = expected_spec.get("variant")
                    actual_variant = specification.get("variant")
                    if expected_variant is not None and actual_variant != expected_variant:
                        self.add_error(
                            artifact.path,
                            f"agents.{agent_id}.variant {actual_variant!r} does not match profile {selected_profile!r} ({expected_variant!r})",
                            key=agent_id,
                            text=artifact.text,
                        )

    @staticmethod
    def _unsupported_parameter_paths(value: Any, path: str) -> list[str]:
        """Find sampling overrides that are unsupported by the thinking model."""

        paths: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    continue
                child_path = f"{path}.{key}" if path else key
                normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", key)
                normalized = normalized.casefold().replace("-", "_")
                if normalized in UNSUPPORTED_THINKING_PARAMETERS:
                    paths.append(child_path)
                paths.extend(Validator._unsupported_parameter_paths(child, child_path))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                paths.extend(
                    Validator._unsupported_parameter_paths(child, f"{path}[{index}]")
                )
        return paths

    def validate_fixer_model_contract(
        self,
        omo_artifact: Artifact,
        profiles: dict[str, dict[str, Any]],
        opencode_artifact: Artifact | None,
        model_catalog: set[str],
        overview_artifact: Artifact | None = None,
    ) -> None:
        """Validate GPT-5.6 Luna fixer model wiring under the bf-o provider."""

        for profile_name in REQUIRED_PROFILES:
            profile = profiles.get(profile_name)
            if profile is None:
                continue
            fixer_spec = profile.get("fixer")
            fixer_model = fixer_spec.get("model") if isinstance(fixer_spec, dict) else None
            if fixer_model != FIXER_MODEL:
                profile_path = self.root / "profiles" / "models" / f"{profile_name}.yml"
                self.add_error(
                    profile_path,
                    f"profile {profile_name!r}.fixer must be {FIXER_MODEL!r}",
                    key="fixer",
                )

        omo = self.require_mapping(omo_artifact, "oh-my-opencode-slim.json")
        if omo is not None:
            presets = omo.get("presets")
            bifrost = presets.get("bifrost") if isinstance(presets, dict) else None
            fixer = bifrost.get("fixer") if isinstance(bifrost, dict) else None
            if not isinstance(fixer, dict):
                self.add_error(
                    omo_artifact.path,
                    "presets.bifrost.fixer must be a mapping for model validation",
                    key="fixer",
                    text=omo_artifact.text,
                )
            else:
                if fixer.get("model") != FIXER_MODEL:
                    self.add_error(
                        omo_artifact.path,
                        f"presets.bifrost.fixer.model must be {FIXER_MODEL!r}",
                        key="model",
                        text=omo_artifact.text,
                    )
                if fixer.get("variant") != "high":
                    self.add_error(
                        omo_artifact.path,
                        "presets.bifrost.fixer.variant must preserve the high variant",
                        key="variant",
                        text=omo_artifact.text,
                    )
                if fixer.get("skills") != ["fixer"]:
                    self.add_error(
                        omo_artifact.path,
                        "presets.bifrost.fixer.skills must remain exactly ['fixer']",
                        key="skills",
                        text=omo_artifact.text,
                    )
                if fixer.get("mcps") != []:
                    self.add_error(
                        omo_artifact.path,
                        "presets.bifrost.fixer.mcps must remain exactly []",
                        key="mcps",
                        text=omo_artifact.text,
                    )
                for field in ("role", "prompt", "permission", "permissions"):
                    if field in fixer:
                        self.add_error(
                            omo_artifact.path,
                            f"presets.bifrost.fixer must not override inherited {field}",
                            key=field,
                            text=omo_artifact.text,
                        )
                for parameter_path in self._unsupported_parameter_paths(fixer, "presets.bifrost.fixer"):
                    self.add_error(
                        omo_artifact.path,
                        f"unsupported thinking-model sampling override {parameter_path!r}",
                        key=parameter_path.rsplit(".", 1)[-1],
                        text=omo_artifact.text,
                    )

        if opencode_artifact is None:
            return
        opencode = self.require_mapping(opencode_artifact, "opencode.json")
        if opencode is None:
            return
        if FIXER_MODEL not in model_catalog:
            self.add_error(
                opencode_artifact.path,
                f"provider catalog must contain exact fixer model {FIXER_MODEL!r}",
                key="models",
                text=opencode_artifact.text,
            )

        providers = opencode.get("provider")
        if not isinstance(providers, dict):
            self.add_error(
                opencode_artifact.path,
                "provider must be a mapping",
                key="provider",
                text=opencode_artifact.text,
            )
            return

        # Validate the fixer model entry under its provider (bf-o).
        fixer_provider_spec = providers.get(FIXER_PROVIDER)
        if not isinstance(fixer_provider_spec, dict):
            self.add_error(
                opencode_artifact.path,
                f"provider.{FIXER_PROVIDER} must be a mapping for the fixer model",
                key=FIXER_PROVIDER,
                text=opencode_artifact.text,
            )
            return

        provider_models = fixer_provider_spec.get("models")
        if not isinstance(provider_models, dict):
            self.add_error(
                opencode_artifact.path,
                f"provider.{FIXER_PROVIDER}.models must be a mapping",
                key="models",
                text=opencode_artifact.text,
            )
        else:
            fixer_entry = provider_models.get(FIXER_MODEL_KEY)
            if not isinstance(fixer_entry, dict):
                self.add_error(
                    opencode_artifact.path,
                    f"provider.{FIXER_PROVIDER}.models must define {FIXER_MODEL_KEY!r}",
                    key="models",
                    text=opencode_artifact.text,
                )
            else:
                # Reasoning must be enabled.
                if fixer_entry.get("reasoning") is not True:
                    self.add_error(
                        opencode_artifact.path,
                        f"fixer model {FIXER_MODEL!r} must have reasoning enabled",
                        key="reasoning",
                        text=opencode_artifact.text,
                    )
                # reasoningEffort must be high.
                reasoning_opts = fixer_entry.get("options")
                if not isinstance(reasoning_opts, dict) or reasoning_opts.get("reasoningEffort") != FIXER_REASONING_EFFORT:
                    self.add_error(
                        opencode_artifact.path,
                        f"fixer model {FIXER_MODEL!r} must preserve reasoningEffort={FIXER_REASONING_EFFORT!r}",
                        key="reasoningEffort",
                        text=opencode_artifact.text,
                    )
                for parameter_path in self._unsupported_parameter_paths(
                    fixer_entry, f"provider.{FIXER_PROVIDER}.models.{FIXER_MODEL_KEY}"
                ):
                    self.add_error(
                        opencode_artifact.path,
                        f"unsupported thinking-model sampling override {parameter_path!r}",
                        key=parameter_path.rsplit(".", 1)[-1],
                        text=opencode_artifact.text,
                    )
                # The fixer model must not use interleaved (that is a
                # Novita-specific legacy mechanism; bf-o uses native reasoning).
                if "interleaved" in fixer_entry:
                    self.add_error(
                        opencode_artifact.path,
                        f"fixer model {FIXER_MODEL!r} must not use interleaved under bf-o",
                        key="interleaved",
                        text=opencode_artifact.text,
                    )

        # Validate every Bifrost provider key has its base URL and credentials.
        for provider_id in (FIXER_PROVIDER, "bf", "bf-a"):
            spec = providers.get(provider_id)
            if not isinstance(spec, dict):
                continue
            opts = spec.get("options")
            if not isinstance(opts, dict):
                self.add_error(
                    opencode_artifact.path,
                    f"provider.{provider_id}.options must preserve the Bifrost connection settings",
                    key="options",
                    text=opencode_artifact.text,
                )
                continue
            if opts.get("apiKey") != BIFROST_CREDENTIAL_REFERENCE:
                self.add_error(
                    opencode_artifact.path,
                    f"provider.{provider_id}.options.apiKey must preserve {BIFROST_CREDENTIAL_REFERENCE!r}",
                    key="apiKey",
                    text=opencode_artifact.text,
                )

        if overview_artifact is not None:
            overview = self.require_mapping(overview_artifact, "agents-overview/data.yaml")
            nodes = overview.get("nodes") if overview else None
            fixer_node = next(
                (
                    node
                    for node in nodes
                    if isinstance(node, dict) and node.get("id") == "fixer"
                ),
                None,
            ) if isinstance(nodes, list) else None
            if not isinstance(fixer_node, dict):
                self.add_error(
                    overview_artifact.path,
                    "overview fixer node is required for role validation",
                    key="fixer",
                    text=overview_artifact.text,
                )
            else:
                if fixer_node.get("role") != "Implementation Specialist":
                    self.add_error(
                        overview_artifact.path,
                        "overview fixer role must remain Implementation Specialist",
                        key="role",
                        text=overview_artifact.text,
                    )
                constraints = fixer_node.get("constraints")
                if not isinstance(constraints, str) or "required handoff fields" not in constraints:
                    self.add_error(
                        overview_artifact.path,
                        "overview fixer constraints must preserve the handoff prompt",
                        key="constraints",
                        text=overview_artifact.text,
                    )

        fixer_skill_path = self.root / ".rulesync" / "skills" / "fixer" / "SKILL.md"
        fixer_skill_text = self.read_text(fixer_skill_path)
        if fixer_skill_text is not None:
            required_prompt_markers = (
                "**Role**: Execute code changes efficiently.",
                "Every fixer task dispatch carries these required fields",
                "`Files` is a hard write allowlist",
                "OpenCode does not expose a dynamic",
                "per-task filesystem ACL",
            )
            missing_markers = [
                marker for marker in required_prompt_markers if marker not in fixer_skill_text
            ]
            if missing_markers:
                self.add_error(
                    fixer_skill_path,
                    "fixer prompt/permission contract is missing: "
                    + ", ".join(missing_markers),
                    key="Role",
                    text=fixer_skill_text,
                )

        fixer_append_path = (
            self.root / ".rulesync" / "oh-my-opencode-slim" / "fixer_append.md"
        )
        fixer_append_text = self.read_text(fixer_append_path)
        if fixer_append_text is not None:
            required_append_markers = (
                "# Fixer — Implementation Specialist",
                "Always use zsh. Source `~/.zshrc` before running commands.",
                "Always run lint validation (check-only, no autofix)",
            )
            missing_markers = [
                marker
                for marker in required_append_markers
                if marker not in fixer_append_text
            ]
            if missing_markers:
                self.add_error(
                    fixer_append_path,
                    "OMO fixer prompt contract is missing: "
                    + ", ".join(missing_markers),
                    key="Fixer",
                    text=fixer_append_text,
                )

        enabled_providers = opencode.get("enabled_providers")
        if not isinstance(enabled_providers, list) or FIXER_PROVIDER not in enabled_providers:
            self.add_error(
                opencode_artifact.path,
                f"enabled_providers must include {FIXER_PROVIDER!r} for the fixer model",
                key="enabled_providers",
                text=opencode_artifact.text,
            )

        # interleaved is a Novita-specific mechanism. Only the bf provider
        # models may have it (legacy backward compat). No model under bf-o,
        # bf-a, or any provider other than bf may declare interleaved.
        for provider_id, provider in providers.items():
            if not isinstance(provider, dict) or not isinstance(provider.get("models"), dict):
                continue
            for model_id, model in provider["models"].items():
                if (
                    isinstance(model_id, str)
                    and isinstance(model, dict)
                    and "interleaved" in model
                    and (
                        provider_id != "bf"
                        or model_id != "huggingface/novita/deepseek-ai/DeepSeek-V4-Pro"
                    )
                ):
                    self.add_error(
                        opencode_artifact.path,
                        "interleaved reasoning configuration is only allowed on the legacy Novita DeepSeek-V4-Pro model",
                        key="interleaved",
                        text=opencode_artifact.text,
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
            version = data.get("version")
            if version != PROFILE_SCHEMA_VERSION:
                self.add_error(
                    artifact.path,
                    f"profile {profile_name!r} schema version must be "
                    f"{PROFILE_SCHEMA_VERSION}, got {version!r}",
                    key="version",
                    text=artifact.text,
                )
                continue
            agents = data.get("agents")
            if not isinstance(agents, dict):
                self.add_error(
                    artifact.path,
                    f"profile {profile_name!r}.agents must be a mapping",
                    key="agents",
                    text=artifact.text,
                )
                continue
            profile_agents: dict[str, Any] = {}
            # Validate every agent entry
            for agent_id, spec in agents.items():
                if not isinstance(agent_id, str) or not agent_id:
                    self.add_error(
                        artifact.path,
                        f"profile {profile_name!r} agent keys must be non-empty strings",
                        key=str(agent_id),
                        text=artifact.text,
                    )
                    continue
                if not isinstance(spec, dict):
                    self.add_error(
                        artifact.path,
                        f"profile {profile_name!r}.{agent_id} must be a mapping",
                        key=agent_id,
                        text=artifact.text,
                    )
                    continue
                model = spec.get("model")
                if not isinstance(model, str) or not model:
                    self.add_error(
                        artifact.path,
                        f"profile {profile_name!r}.{agent_id}.model must be a non-empty string",
                        key=agent_id,
                        text=artifact.text,
                    )
                    continue
                if model not in model_catalog:
                    self.add_error(
                        artifact.path,
                        f"profile {profile_name!r}.{agent_id}.model references unknown model {model!r}",
                        key=agent_id,
                        text=artifact.text,
                    )
                profile_agents[agent_id] = {
                    "model": model,
                }
                if "variant" in spec:
                    variant = spec["variant"]
                    if not isinstance(variant, str) or not variant:
                        self.add_error(
                            artifact.path,
                            f"profile {profile_name!r}.{agent_id}.variant "
                            f"must be a non-empty string or absent, got {variant!r}",
                            key=agent_id,
                            text=artifact.text,
                        )
                    else:
                        profile_agents[agent_id]["variant"] = variant
            profiles[profile_name] = profile_agents
            self.compare_sets(
                artifact.path,
                f"profile {profile_name!r} agent keys",
                configured_agents,
                profile_agents.keys(),
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
                # overview emits {agent_id: model_name} from the new schema.
                # Build expected overview shape: agent_id -> model string.
                expected_overview = {
                    agent_id: info["model"]
                    for agent_id, info in expected.items()
                }
                if actual != expected_overview:
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
        source_contracts: dict[str, dict[str, Any]] = {}
        source_paths = sorted(source_dir.glob("*.md")) if source_dir.is_dir() else []
        for path in source_paths:
            artifact = self._load_frontmatter(path)
            if artifact is None:
                continue
            metadata = self.require_mapping(artifact, "agent frontmatter")
            if metadata is None:
                continue
            self.validate_agent_contract_fields(path, artifact, metadata)
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
            source_contracts[name] = self.agent_contract(metadata)
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
        generated_contracts: dict[str, dict[str, Any]] = {}
        for path in (
            sorted(generated_dir.glob("*.md")) if generated_dir.is_dir() else []
        ):
            artifact = self._load_frontmatter(path)
            if artifact is None:
                continue
            metadata = self.require_mapping(artifact, "generated agent frontmatter")
            if metadata is None:
                continue
            self.validate_generated_agent_contract(path, artifact, metadata)
            name = metadata.get("name")
            if not isinstance(name, str) or not name:
                continue
            if name in generated_names:
                self.add_error(
                    path,
                    f"duplicate generated subagent {name!r}",
                    key="name",
                    text=artifact.text,
                )
            generated_names.add(name)
            generated_contracts[name] = self.agent_contract(metadata)
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
        for name in sorted(source_names & generated_names):
            source_contract = source_contracts[name]
            generated_contract = generated_contracts[name]
            for field, expected in source_contract.items():
                # Rulesync may normalize or omit optional source metadata in
                # generated frontmatter. Compare only fields represented by
                # both contracts; generated-only fields remain allowed.
                if field in generated_contract and generated_contract[field] != expected:
                    self.add_error(
                        self.payload / "agents" / f"{name}.md",
                        f"generated agent {name!r}.{field} does not match source contract",
                        key=field,
                    )

    @staticmethod
    def agent_contract(metadata: dict[str, Any]) -> dict[str, Any]:
        """Select source-owned fields while allowing Rulesync output additions."""

        return {
            field: metadata[field]
            for field in AGENT_CONTRACT_FIELDS
            if field in metadata
        }

    def validate_generated_agent_contract(
        self, path: Path, artifact: Artifact, metadata: dict[str, Any]
    ) -> None:
        """Validate required generated identity and present contract field shapes."""

        for field in REQUIRED_GENERATED_AGENT_FIELDS:
            if field not in metadata:
                self.add_error(
                    path,
                    f"generated agent frontmatter {field!r} is required",
                    key=field,
                    text=artifact.text,
                )
        self.validate_agent_contract_fields(path, artifact, metadata)

    def validate_agent_contract_fields(
        self, path: Path, artifact: Artifact, metadata: dict[str, Any]
    ) -> None:
        """Validate the type and shape of every present contract field."""

        for field in AGENT_CONTRACT_FIELDS:
            if field not in metadata:
                continue
            value = metadata[field]
            shape = AGENT_CONTRACT_FIELD_SHAPES[field]
            valid = (
                isinstance(value, str) and bool(value)
                if shape == "non_empty_string"
                else isinstance(value, list)
                and all(isinstance(item, str) and bool(item) for item in value)
                if shape == "string_list"
                else isinstance(value, dict)
                if shape == "mapping"
                else False
            )
            if not valid:
                self.add_error(
                    path,
                    f"agent contract field {field!r} has invalid shape; expected {shape}",
                    key=field,
                    text=artifact.text,
                )

    def _load_frontmatter(self, path: Path, *, kind: str = "agent") -> Artifact | None:
        text = self.read_text(path)
        if text is None:
            return None
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            self.add_error(path, f"{kind} file must start with YAML frontmatter", line=1)
            return None
        end = next(
            (index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"),
            None,
        )
        if end is None:
            self.add_error(path, f"{kind} frontmatter is not closed", line=1)
            return None
        frontmatter = "".join(lines[1:end])
        if yaml is None:
            self.add_error(path, f"PyYAML is required to parse {kind} frontmatter")
            return None
        try:
            data = yaml.safe_load(frontmatter)
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            line = mark.line + 2 if mark else None
            self.add_error(path, f"invalid {kind} frontmatter YAML: {error}", line=line)
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
        reviewer_lanes = [*REVIEWER_LANES]
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

        for node_id, node in nodes_by_id.items():
            parent = node.get("parent")
            if parent is not None and (
                not isinstance(parent, str) or parent not in nodes_by_id
            ):
                self.add_error(
                    artifact.path,
                    f"overview node {node_id!r} references unknown parent {parent!r}",
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

        orchestrator = nodes_by_id.get("orchestrator")
        if not isinstance(orchestrator, dict) or orchestrator.get("type") != "agent":
            self.add_error(
                artifact.path,
                "overview OpenCode orchestrator agent node is missing",
                key="orchestrator",
                text=artifact.text,
            )
        else:
            if orchestrator.get("orchestrates") is not True:
                self.add_error(
                    artifact.path,
                    "overview OpenCode orchestrator must declare orchestrates: true",
                    key="orchestrator",
                    text=artifact.text,
                )

            review_ownership = orchestrator.get("review_ownership")
            if not isinstance(review_ownership, str) or not all(
                marker in review_ownership
                for marker in ("OpenCode", "sole coordinator", REVIEWER_COORDINATOR)
            ):
                self.add_error(
                    artifact.path,
                    "overview OpenCode orchestrator is missing reviewer coordinator ownership metadata",
                    key="review_ownership",
                    text=artifact.text,
                )

            orchestrator_dispatches = orchestrator.get("dispatches")
            if not isinstance(orchestrator_dispatches, list):
                self.add_error(
                    artifact.path,
                    "overview OpenCode orchestrator.dispatches must be a list",
                    key="dispatches",
                    text=artifact.text,
                )
            else:
                self.validate_opencode_reviewer_dispatches(
                    artifact.path,
                    "overview OpenCode orchestrator.dispatches",
                    orchestrator_dispatches,
                    text=artifact.text,
                )

        if "reviewer" in nodes_by_id:
            self.add_error(
                artifact.path,
                "overview contains an active legacy reviewer coordinator alias",
                key="reviewer",
                text=artifact.text,
            )
        coordinator = nodes_by_id.get(REVIEWER_COORDINATOR)
        if not isinstance(coordinator, dict) or coordinator.get("type") != "agent":
            self.add_error(
                artifact.path,
                f"overview {REVIEWER_COORDINATOR} agent node is missing",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )
        else:
            dispatches = coordinator.get("dispatches")
            if not isinstance(dispatches, list):
                self.add_error(
                    artifact.path,
                    f"overview {REVIEWER_COORDINATOR}.dispatches must be a list",
                    key="dispatches",
                    text=artifact.text,
                )
            else:
                reviewer_dispatches = self.validate_reviewer_coordinator_dispatches(
                    artifact.path,
                    f"overview {REVIEWER_COORDINATOR}.dispatches",
                    dispatches,
                    text=artifact.text,
                )
                self.compare_sets(
                    artifact.path,
                    f"overview {REVIEWER_COORDINATOR} dispatches",
                    reviewer_lanes,
                    reviewer_dispatches,
                    text=artifact.text,
                )

        overview_lane_nodes = {
            node_id
            for node_id, node in nodes_by_id.items()
            if node.get("type") == "agent" and node_id in REVIEWER_LANES
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
            if (
                not isinstance(link, dict)
                or link.get("source") != REVIEWER_COORDINATOR
            ):
                continue
            target = link.get("target")
            if isinstance(target, str) and target in REVIEWER_LANES:
                reviewer_links.add(target)
        self.compare_sets(
            artifact.path,
            f"overview {REVIEWER_COORDINATOR} link targets",
            reviewer_lanes,
            reviewer_links,
            text=artifact.text,
        )

        open_code_links: set[str] = set()
        for link in links:
            if not isinstance(link, dict) or link.get("source") != "orchestrator":
                continue
            target = link.get("target")
            if isinstance(target, str) and target in REVIEWER_IDS:
                open_code_links.add(target)
        self.compare_sets(
            artifact.path,
            "overview OpenCode reviewer link targets",
            (REVIEWER_COORDINATOR,),
            open_code_links,
            text=artifact.text,
        )

        for lane in reviewer_lanes:
            node = nodes_by_id.get(lane)
            if isinstance(node, dict) and node.get("parent") != REVIEWER_COORDINATOR:
                self.add_error(
                    artifact.path,
                    f"overview OpenCode reviewer lane {lane!r} must have parent {REVIEWER_COORDINATOR}",
                    key=lane,
                    text=artifact.text,
                )

        lane_nodes = [
            nodes_by_id[lane]
            for lane in reviewer_lanes
            if isinstance(nodes_by_id.get(lane), dict)
        ]
        has_claude_compatibility_metadata = any(
            "claude_parent" in node for node in lane_nodes
        )
        if has_claude_compatibility_metadata:
            for lane in reviewer_lanes:
                node = nodes_by_id.get(lane)
                if not isinstance(node, dict):
                    continue
                if "claude_parent" not in node:
                    self.add_error(
                        artifact.path,
                        f"overview Claude compatibility metadata missing for reviewer lane {lane!r}",
                        key=lane,
                        text=artifact.text,
                    )
                elif node.get("claude_parent") != REVIEWER_COORDINATOR:
                    self.add_error(
                        artifact.path,
                        f"overview reviewer lane {lane!r} claude_parent must be {REVIEWER_COORDINATOR}",
                        key=lane,
                        text=artifact.text,
                    )

        self.validate_reviewer_contracts(reviewer_lanes, reviewer_contract_texts)

    def validate_opencode_reviewer_dispatches(
        self,
        path: Path,
        location: str,
        values: list[Any],
        *,
        text: str,
    ) -> list[str]:
        """Validate reviewer candidates without constraining ordinary dispatches."""

        reviewer_candidates = _reviewer_candidates(values)
        for value in reviewer_candidates:
            if REVIEWER_ID_PATTERN.fullmatch(value) is None:
                self.add_error(
                    path,
                    f"{location} contains malformed reviewer candidate {value!r}; expected reviewer-*",
                    key="dispatches",
                    text=text,
                )

        reviewer_dispatches = _reviewer_shaped_ids(reviewer_candidates)
        for reviewer_id in sorted(set(reviewer_dispatches) - set(REVIEWER_IDS)):
            self.add_error(
                path,
                f"{location} unknown reviewer ID {reviewer_id!r}; use the explicit reviewer registry",
                key="dispatches",
                text=text,
            )

        duplicate_dispatches = sorted(
            {
                reviewer_id
                for reviewer_id in reviewer_candidates
                if reviewer_candidates.count(reviewer_id) > 1
            }
        )
        if duplicate_dispatches:
            self.add_error(
                path,
                f"{location} contains duplicate reviewer IDs: "
                + ", ".join(duplicate_dispatches),
                key="dispatches",
                text=text,
            )

        direct_lane_dispatches = [
            value for value in reviewer_dispatches if value in REVIEWER_LANES
        ]
        if direct_lane_dispatches:
            self.add_error(
                path,
                "overview OpenCode orchestrator must not dispatch reviewer lanes directly: "
                + ", ".join(direct_lane_dispatches),
                key="dispatches",
                text=text,
            )

        coordinator_count = reviewer_dispatches.count(REVIEWER_COORDINATOR)
        if coordinator_count != 1:
            self.add_error(
                path,
                f"{location} must contain exactly one {REVIEWER_COORDINATOR}; got {coordinator_count}",
                key="dispatches",
                text=text,
            )
        return reviewer_dispatches

    def validate_reviewer_coordinator_dispatches(
        self,
        path: Path,
        location: str,
        values: list[Any],
        *,
        text: str,
    ) -> list[str]:
        """Validate the coordinator's complete, ten-lane reviewer dispatch list."""

        for index, value in enumerate(values):
            if not isinstance(value, str):
                self.add_error(
                    path,
                    f"{location}[{index}] must be a string reviewer ID; got {type(value).__name__}",
                    key="dispatches",
                    text=text,
                )
                continue
            if value == REVIEWER_COORDINATOR:
                self.add_error(
                    path,
                    f"{location}[{index}] must not dispatch {REVIEWER_COORDINATOR}",
                    key="dispatches",
                    text=text,
                )
            if REVIEWER_ID_PATTERN.fullmatch(value) is None:
                self.add_error(
                    path,
                    f"{location}[{index}] must match the reviewer ID format reviewer-*; got {value!r}",
                    key="dispatches",
                    text=text,
                )

        # Extract only after every raw entry has received shape validation.
        reviewer_dispatches = _reviewer_shaped_ids(values)

        for reviewer_id in sorted(set(reviewer_dispatches) - set(REVIEWER_IDS)):
            self.add_error(
                path,
                f"{location} unknown reviewer ID {reviewer_id!r}; use the explicit reviewer registry",
                key="dispatches",
                text=text,
            )

        duplicate_dispatches = sorted(
            {
                reviewer_id
                for reviewer_id in reviewer_dispatches
                if reviewer_dispatches.count(reviewer_id) > 1
            }
        )
        if duplicate_dispatches:
            self.add_error(
                path,
                f"{location} contains duplicate reviewer IDs: "
                + ", ".join(duplicate_dispatches),
                key="dispatches",
                text=text,
            )

        if len(values) != len(REVIEWER_LANES):
            self.add_error(
                path,
                f"{location} must contain exactly {len(REVIEWER_LANES)} reviewer IDs; got {len(values)}",
                key="dispatches",
                text=text,
            )

        return [reviewer_id for reviewer_id in reviewer_dispatches if reviewer_id in REVIEWER_LANES]

    def validate_reviewer_contracts(
        self,
        reviewer_lanes: list[str],
        contract_texts: list[tuple[Path, str]],
    ) -> None:
        expected = set(REVIEWER_IDS)
        for path, text in contract_texts:
            references = {
                reviewer_id
                for reviewer_id in REVIEWER_IDS
                if re.search(rf"\b{re.escape(reviewer_id)}\b", text)
            }
            unknown_references = {
                reference
                for reference in re.findall(r"\breviewer-[a-z0-9][a-z0-9-]*\b", text)
                if reference not in REVIEWER_IDS
            }
            self.compare_sets(
                path,
                "reviewer contract lane references",
                expected,
                references,
                text=text,
            )
            for stale in sorted(unknown_references):
                self.add_error(
                    path,
                    f"reviewer contract references unknown lane {stale!r}",
                    key=stale,
                    text=text,
                )

    def validate_reviewer_runtime_health(
        self, contract_texts: list[tuple[Path, str]]
    ) -> None:
        """Require runtime evidence fields in the reviewer report contract."""

        for path, text in contract_texts:
            health_match = re.search(
                r"^##\s+Review Health\s*$([\s\S]*?)(?=^##\s+|\Z)",
                text,
                re.IGNORECASE | re.MULTILINE,
            )
            if health_match is None:
                self.add_error(
                    path,
                    "reviewer health contract must contain a Review Health section",
                    key="Review Health",
                    text=text,
                )
                continue
            normalized = health_match.group(1).casefold()
            missing = [
                field
                for field in REVIEWER_HEALTH_FIELDS
                if field.casefold() not in normalized
            ]
            if missing:
                self.add_error(
                    path,
                    "reviewer health contract is missing runtime fields: "
                    + ", ".join(missing),
                    key="Review Health",
                    text=text,
                )
            if "runtime smoke evidence" not in normalized or "failed" not in normalized:
                self.add_error(
                    path,
                    "reviewer health contract must degrade on failed smoke evidence",
                    key="runtime smoke evidence",
                    text=text,
                )
            if (
                "effective permission evidence" not in normalized
                or "mismatch" not in normalized
            ):
                self.add_error(
                    path,
                    "reviewer health contract must degrade on effective permission mismatch",
                    key="runtime smoke evidence",
                    text=text,
                )

    def validate_fixer_scheduler_contract(self, overview_artifact: Artifact | None) -> None:
        """Validate the source and staged guidance for bounded fixer batches."""

        source_paths = (
            self.root / ".rulesync" / "oh-my-opencode-slim" / "orchestrator_append.md",
            self.root / ".rulesync" / "rules" / "custom-rules.md",
            self.root / ".rulesync" / "skills" / "executing-plans" / "SKILL.md",
            self.root / ".rulesync" / "skills" / "fixer" / "SKILL.md",
            self.root / ".rulesync" / "skills" / "writing-plans" / "SKILL.md",
            self.root / ".rulesync" / "skills" / "deepwork" / "SKILL.md",
        )
        texts: list[tuple[Path, str]] = []
        for path in source_paths:
            text = self.read_text(path)
            if text is not None:
                texts.append((path, text))

        if self.payload:
            staged_paths = (
                self.payload / "AGENTS.md",
                self.payload / "skills" / "executing-plans" / "SKILL.md",
                self.payload / "skills" / "fixer" / "SKILL.md",
                self.payload / "skills" / "writing-plans" / "SKILL.md",
                self.payload / "skills" / "deepwork" / "SKILL.md",
            )
            for path in staged_paths:
                if path.is_file():
                    text = self.read_text(path)
                    if text is not None:
                        texts.append((path, text))

        combined = "\n".join(text for _, text in texts).casefold()
        requirements = (
            (
                re.compile(r"(?:at most|maximum|max(?:imum)?|cap).{0,100}\b3\b"),
                "scheduler guidance must cap concurrent fixer children at 3",
            ),
            (
                re.compile(r"background\s*[=:]\s*true|background=true"),
                "scheduler guidance must require background=true dispatch",
            ),
            (
                re.compile(r"exact(?:ly)? returned session id|exact returned.*session id"),
                "scheduler guidance must reconcile exact returned session IDs",
            ),
            (re.compile(r"\btask_result\b"), "scheduler guidance must use task_result reconciliation"),
            (
                re.compile(r"hard.{0,30}files.{0,30}allowlist|files.{0,30}hard write allowlist"),
                "scheduler guidance must define a hard Files write allowlist",
            ),
            (
                re.compile(r"overlap.{0,80}ambiguous|ambiguous.{0,80}overlap"),
                "scheduler guidance must serialize overlapping or ambiguous work",
            ),
            (
                re.compile(r"generated.{0,80}lockfile|lockfile.{0,80}generated"),
                "scheduler guidance must address generated outputs and lockfiles",
            ),
            (
                re.compile(r"needs_context.{0,120}blocked|blocked.{0,120}needs_context"),
                "scheduler guidance must hold dependents for NEEDS_CONTEXT and BLOCKED",
            ),
            (
                re.compile(r"timeout.{0,120}failure|failure.{0,120}timeout"),
                "scheduler guidance must hold dependents for timeout and failure",
            ),
            (
                re.compile(r"every.{0,80}done.{0,100}review|per-child review"),
                "scheduler guidance must require a review gate for every DONE child",
            ),
        )
        if not texts:
            self.add_error(
                self.root / ".rulesync",
                "fixer scheduler source guidance is unavailable",
            )
        for pattern, message in requirements:
            if pattern.search(combined) is None:
                path = texts[0][0] if texts else self.root / ".rulesync"
                self.add_error(path, message)

        if overview_artifact is None:
            return
        overview = self.require_mapping(overview_artifact, "agents-overview/data.yaml")
        nodes = overview.get("nodes") if overview else None
        orchestrator = next(
            (
                node
                for node in nodes
                if isinstance(node, dict) and node.get("id") == "orchestrator"
            ),
            None,
        ) if isinstance(nodes, list) else None
        scheduler = orchestrator.get("fixer_scheduler") if isinstance(orchestrator, dict) else None
        if not isinstance(scheduler, dict):
            self.add_error(
                overview_artifact.path,
                "overview orchestrator must define fixer_scheduler metadata",
                key="fixer_scheduler",
                text=overview_artifact.text,
            )
            return
        if scheduler.get("max_concurrent_children") != FIXER_BATCH_MAX:
            self.add_error(
                overview_artifact.path,
                "overview fixer_scheduler.max_concurrent_children must be 3",
                key="max_concurrent_children",
                text=overview_artifact.text,
            )
        for key in (
            "dispatch",
            "lifecycle",
            "dependency_policy",
            "failure_policy",
            "ownership_policy",
        ):
            if not isinstance(scheduler.get(key), str) or not scheduler[key].strip():
                self.add_error(
                    overview_artifact.path,
                    f"overview fixer_scheduler.{key} must be a non-empty string",
                    key=key,
                    text=overview_artifact.text,
                )

    def _manifest_path(
        self,
        root: Path,
        value: Any,
        manifest: Path,
        *,
        allow_final_symlink: bool = False,
    ) -> Path | None:
        """Validate a manifest path without following symlinks out of root.

        When ``allow_final_symlink`` is true, a symlink at the managed path
        itself is left for the caller to report (e.g. with a ``symlink``
        diagnostic) instead of being rejected here. Intermediate-directory
        symlinks remain path-safety errors in every case.
        """

        if not isinstance(value, str) or not value:
            self.add_error(manifest, "manifest paths must be non-empty strings")
            return None
        if "\x00" in value or "\\" in value:
            self.add_error(manifest, f"manifest path is not portable: {value!r}")
            return None
        path = Path(value)
        parts = value.split("/")
        if path.is_absolute() or value.startswith("/") or any(
            part in ("", ".", "..") for part in parts
        ):
            self.add_error(
                manifest,
                f"manifest path must be a safe relative path: {value!r}",
            )
            return None

        root = root.resolve()
        candidate = root.joinpath(*parts)
        try:
            candidate.resolve(strict=False).relative_to(root)
        except ValueError:
            self.add_error(
                manifest,
                f"manifest path escapes the OpenCode config directory: {value!r}",
            )
            return None
        current = root
        for index, part in enumerate(parts):
            current /= part
            is_final = index == len(parts) - 1
            if current.is_symlink() and not (allow_final_symlink and is_final):
                self.add_error(
                    manifest,
                    f"manifest path traverses a symlink: {value!r}",
                )
                return None
        return candidate

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _manifest_file_diagnostic(
        self,
        manifest_path: Path,
        value: str,
        status: str,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        """Emit one deterministic managed-file mismatch diagnostic.

        Exposes the relative managed path, an explicit status, the manifest's
        expected SHA-256 (or ``<none>`` when absent/invalid) and the actual
        value: a real digest for ``changed`` files, or a ``<missing>`` /
        ``<symlink>`` / ``<not-regular>`` placeholder for paths that must not
        be hashed or read. Never emits file contents.
        """

        expected = (
            expected_hash
            if re.fullmatch(r"[0-9a-f]{64}", expected_hash or "") is not None
            else "<none>"
        )
        self.add_error(
            manifest_path,
            f"manifest managed file {status}: path={value} "
            f"expected_sha256={expected} actual_sha256={actual_hash}",
        )

    def validate_opencode_manifest(
        self,
        manifest_path: Path,
        config_path: Path,
        *,
        require_present: bool,
    ) -> None:
        """Validate ownership metadata and, when available, its file hashes."""

        if manifest_path.is_symlink():
            self.add_error(manifest_path, "OpenCode ownership manifest must not be a symlink")
            return
        if config_path.is_symlink() or not config_path.is_dir():
            self.add_error(
                config_path,
                "OpenCode config path must be a regular directory",
            )
            return
        artifact = self.load_json(manifest_path)
        if artifact is None:
            return
        manifest = self.require_mapping(artifact, "OpenCode ownership manifest")
        if manifest is None:
            return
        if manifest.get("managed_by") != OPENCODE_MANAGED_BY:
            self.add_error(
                manifest_path,
                f"manifest managed_by must be {OPENCODE_MANAGED_BY!r}",
                key="managed_by",
                text=artifact.text,
            )
        if manifest.get("version") != OPENCODE_MANIFEST_VERSION:
            self.add_error(
                manifest_path,
                f"manifest version must be {OPENCODE_MANIFEST_VERSION}",
                key="version",
                text=artifact.text,
            )
        if not isinstance(manifest.get("timestamp"), str) or not manifest["timestamp"]:
            self.add_error(
                manifest_path,
                "manifest timestamp must be a non-empty string",
                key="timestamp",
                text=artifact.text,
            )

        files = manifest.get("managed_files")
        directories = manifest.get("managed_directories")
        hashes = manifest.get("managed_file_hashes")
        if not isinstance(files, list) or not isinstance(directories, list):
            self.add_error(
                manifest_path,
                "manifest managed_files and managed_directories must be lists",
                key="managed_files",
                text=artifact.text,
            )
            return
        if not all(isinstance(value, str) for value in [*files, *directories]):
            self.add_error(
                manifest_path,
                "manifest managed paths must be strings",
                key="managed_files",
                text=artifact.text,
            )
        files = [value for value in files if isinstance(value, str)]
        directories = [value for value in directories if isinstance(value, str)]
        if len(set(files)) != len(files) or len(set(directories)) != len(directories):
            self.add_error(
                manifest_path,
                "manifest contains duplicate managed paths",
                key="managed_files",
                text=artifact.text,
            )
        if set(files) & set(directories):
            self.add_error(
                manifest_path,
                "manifest path cannot be both a file and a directory",
                key="managed_files",
                text=artifact.text,
            )
        if not isinstance(hashes, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in (hashes.items() if isinstance(hashes, dict) else [])
        ):
            self.add_error(
                manifest_path,
                "manifest managed_file_hashes must be a mapping of strings",
                key="managed_file_hashes",
                text=artifact.text,
            )
            hashes = {}
        hashes = {
            key: value
            for key, value in hashes.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        invalid_hashes = [
            key
            for key, value in hashes.items()
            if re.fullmatch(r"[0-9a-f]{64}", value) is None
        ]
        if invalid_hashes:
            self.add_error(
                manifest_path,
                "manifest file hashes must be lowercase SHA-256 values: "
                + ", ".join(sorted(invalid_hashes)),
                key="managed_file_hashes",
                text=artifact.text,
            )
        if set(hashes) != set(files):
            self.add_error(
                manifest_path,
                "manifest file hashes must exactly match managed_files",
                key="managed_file_hashes",
                text=artifact.text,
            )

        validated_files: dict[str, Path] = {}
        validated_directories: dict[str, Path] = {}
        for value in files:
            candidate = self._manifest_path(
                config_path, value, manifest_path, allow_final_symlink=True
            )
            if candidate is None:
                continue
            validated_files[value] = candidate
            if not candidate.exists() and not candidate.is_symlink():
                if require_present:
                    self._manifest_file_diagnostic(
                        manifest_path,
                        value,
                        "missing",
                        hashes.get(value, ""),
                        "<missing>",
                    )
            elif candidate.is_symlink():
                self._manifest_file_diagnostic(
                    manifest_path,
                    value,
                    "symlink",
                    hashes.get(value, ""),
                    "<symlink>",
                )

        for value in directories:
            candidate = self._manifest_path(config_path, value, manifest_path)
            if candidate is None:
                continue
            validated_directories[value] = candidate
            if require_present and not candidate.exists():
                self.add_error(manifest_path, f"manifest managed path is missing: {value}")
            elif candidate.is_symlink():
                self.add_error(manifest_path, f"manifest managed path is a symlink: {value}")

        for value in directories:
            candidate = validated_directories.get(value)
            if candidate is None:
                continue
            if require_present and candidate.exists() and not candidate.is_dir():
                self.add_error(
                    manifest_path,
                    f"manifest managed directory is not a directory: {value}",
                )
        for value in files:
            candidate = validated_files.get(value)
            if candidate is None:
                continue
            if not require_present:
                continue
            if candidate.is_symlink() or not candidate.exists():
                # Already reported in the first pass.
                continue
            if not candidate.is_file():
                self._manifest_file_diagnostic(
                    manifest_path,
                    value,
                    "not-regular",
                    hashes.get(value, ""),
                    "<not-regular>",
                )
            elif re.fullmatch(r"[0-9a-f]{64}", hashes.get(value, "")):
                try:
                    actual_hash = self._sha256(candidate)
                except OSError as error:
                    self.add_error(manifest_path, f"cannot hash managed file {value}: {error}")
                    continue
                if actual_hash != hashes[value]:
                    self._manifest_file_diagnostic(
                        manifest_path,
                        value,
                        "changed",
                        hashes[value],
                        actual_hash,
                    )

        if self.payload and config_path == self.payload:
            expected_files: set[str] = set()
            expected_directories: set[str] = set()
            for path in self.payload.rglob("*"):
                relative = path.relative_to(self.payload).as_posix()
                if relative == OPENCODE_MANIFEST_NAME:
                    continue
                if path.is_symlink():
                    self.add_error(manifest_path, f"staged payload contains a symlink: {relative}")
                elif path.is_file():
                    expected_files.add(relative)
                elif path.is_dir():
                    expected_directories.add(relative)
            self.compare_sets(
                manifest_path,
                "manifest managed files",
                expected_files,
                files,
                text=artifact.text,
            )
            self.compare_sets(
                manifest_path,
                "manifest managed directories",
                expected_directories,
                directories,
                text=artifact.text,
            )

    def validate_reviewer_shadow(
        self, canonical_path: Path, canonical_text: str | None = None
    ) -> None:
        """Report coordinator shadows without mutating unmanaged user files."""

        candidates = (
            Path.home() / ".agents" / "skills" / REVIEWER_COORDINATOR / "SKILL.md",
            Path.home() / ".agents" / "skills" / f"{REVIEWER_COORDINATOR}.md",
            Path.home() / ".agents" / "skills" / REVIEWER_COORDINATOR / "SKILL.mdx",
        )
        stale_candidates = (
            Path.home() / ".agents" / "skills" / "reviewer" / "SKILL.md",
            Path.home() / ".agents" / "skills" / "reviewer.md",
            Path.home() / ".agents" / "skills" / "reviewer" / "SKILL.mdx",
        )
        canonical = (
            canonical_text
            if canonical_text is not None
            else self.read_text(canonical_path)
        )
        if canonical is not None:
            for shadow in candidates:
                if not shadow.exists() and not shadow.is_symlink():
                    continue
                if shadow.is_symlink() or not shadow.is_file():
                    self.add_error(shadow, "reviewer-coordinator shadow entry is not a regular file")
                    continue
                shadow_text = self.read_text(shadow)
                if shadow_text is not None and shadow_text != canonical:
                    self.add_error(
                        shadow,
                        "reviewer-coordinator shadow skill differs from canonical OpenCode skill; reconcile or remove it manually",
                    )
        for shadow in stale_candidates:
            if not shadow.exists() and not shadow.is_symlink():
                continue
            self.add_error(
                shadow,
                "stale reviewer shadow entry found; deploy.sh will not delete unmanaged user content",
            )

    def validate_reviewer_skill_integrity(
        self, canonical_path: Path, staged_path: Path | None = None
    ) -> None:
        """Validate the coordinator skill against its lock entry and payload."""

        lock_path = self.root / "skills-lock.json"
        lock_artifact = self.load_json(lock_path)
        if lock_artifact is None:
            self.add_error(
                lock_path,
                f"skills-lock.json is required to validate {REVIEWER_COORDINATOR} SKILL.md",
            )
            return
        lock = self.require_mapping(lock_artifact, "skills-lock.json")
        skills = lock.get("skills") if lock else None
        if not isinstance(skills, dict):
            self.add_error(
                lock_path,
                "skills-lock.json.skills must be a mapping containing the reviewer-coordinator entry",
                key="skills",
                text=lock_artifact.text,
            )
            return
        entry = skills.get(REVIEWER_COORDINATOR)
        if not isinstance(entry, dict):
            self.add_error(
                lock_path,
                f"skills-lock.json.skills.{REVIEWER_COORDINATOR} must be a mapping",
                key=REVIEWER_COORDINATOR,
                text=lock_artifact.text,
            )
            return

        expected_path = f".rulesync/skills/{REVIEWER_COORDINATOR}/SKILL.md"
        if entry.get("skillPath") != expected_path:
            self.add_error(
                lock_path,
                f"skills-lock.json.skills.{REVIEWER_COORDINATOR}.skillPath must be {expected_path!r}",
                key=REVIEWER_COORDINATOR,
                text=lock_artifact.text,
            )
        expected_hash = entry.get("computedHash")
        if not isinstance(expected_hash, str) or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            self.add_error(
                lock_path,
                f"skills-lock.json.skills.{REVIEWER_COORDINATOR}.computedHash must be a lowercase SHA-256 value",
                key=REVIEWER_COORDINATOR,
                text=lock_artifact.text,
            )
            expected_hash = None

        canonical_hash = None
        if canonical_path.is_file() and not canonical_path.is_symlink():
            try:
                canonical_hash = self._sha256(canonical_path)
            except (OSError, UnicodeDecodeError) as error:
                self.add_error(
                    canonical_path,
                    f"canonical {REVIEWER_COORDINATOR} SKILL.md cannot be hashed: {error}",
                )
            if expected_hash is not None and canonical_hash != expected_hash:
                self.add_error(
                    canonical_path,
                    f"canonical {REVIEWER_COORDINATOR} SKILL.md SHA-256 {canonical_hash!r} does not match skills-lock.json computedHash {expected_hash!r}",
                )

        if staged_path is None or not staged_path.is_file() or staged_path.is_symlink():
            return
        if canonical_hash is None:
            return
        canonical_artifact = self._load_frontmatter(canonical_path, kind="skill")
        staged_artifact = self._load_frontmatter(staged_path, kind="staged skill")
        if canonical_artifact is None or staged_artifact is None:
            return

        if canonical_artifact.data != staged_artifact.data:
            self.add_error(
                staged_path,
                f"staged {REVIEWER_COORDINATOR} SKILL.md frontmatter differs from canonical skill",
            )
        if self._normalized_skill_body(canonical_artifact.text) != self._normalized_skill_body(
            staged_artifact.text
        ):
            self.add_error(
                staged_path,
                f"staged {REVIEWER_COORDINATOR} SKILL.md Markdown body differs from canonical skill",
            )

    def load_required_reviewer_skill(
        self, path: Path, label: str
    ) -> str | None:
        """Load a required coordinator skill and reject unusable files explicitly."""

        if not path.exists() and not path.is_symlink():
            self.add_error(
                path,
                f"{label} SKILL.md is missing; expected a non-empty regular file",
            )
            return None
        if path.is_symlink() or not path.is_file():
            self.add_error(
                path,
                f"{label} SKILL.md must be a non-empty regular file",
            )
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            self.add_error(
                path,
                f"{label} SKILL.md cannot be read as UTF-8: {error}",
            )
            return None
        if not text.strip():
            self.add_error(path, f"{label} SKILL.md must not be empty")
            return None
        return text

    def validate_reviewer_registry_references(
        self,
        artifact: Artifact,
        location: str,
        text: str,
    ) -> None:
        """Require reviewer references to use the explicit shared registry."""

        reviewer_shaped_references = _reviewer_shaped_references(text)
        unknown_reviewer_references = sorted(
            set(reviewer_shaped_references) - set(REVIEWER_IDS)
        )
        for reviewer_id in unknown_reviewer_references:
            self.add_error(
                artifact.path,
                f"{location} references unknown reviewer ID {reviewer_id!r}",
                key=location.split(".")[-1],
                text=artifact.text,
            )
        references = {
            reviewer_id
            for reviewer_id in REVIEWER_IDS
            if re.search(rf"\b{re.escape(reviewer_id)}\b", text)
        }
        self.compare_sets(
            artifact.path,
            f"{location} registry references",
            REVIEWER_IDS,
            references,
            text=artifact.text,
        )

    def validate_reviewer_lane_prompts(
        self,
        artifact: Artifact,
        reviewer_lanes: list[str],
        agents: dict[str, dict[str, Any]],
    ) -> None:
        coordinator = agents.get(REVIEWER_COORDINATOR)
        if coordinator:
            for field in ("prompt", "orchestratorPrompt"):
                prompt = coordinator.get(field)
                if not isinstance(prompt, str):
                    self.add_error(
                        artifact.path,
                        f"agents.{REVIEWER_COORDINATOR}.{field} must be a string",
                        key=REVIEWER_COORDINATOR,
                        text=artifact.text,
                    )
                    continue
                self.validate_reviewer_registry_references(
                    artifact,
                    f"agents.{REVIEWER_COORDINATOR}.{field}",
                    prompt,
                )
                if field != "prompt":
                    continue
                if (
                    not all(lane in prompt for lane in REVIEWER_PHASE_A_LANES)
                    or not (
                        "sequential Phase B" in prompt
                        or ("sequentially" in prompt and "Phase B" in prompt)
                    )
                    or "reviewer-simplifier" not in prompt
                ):
                    self.add_error(
                        artifact.path,
                        "runtime reviewer coordinator prompt must describe all Phase A lanes and the sequential reviewer-simplifier Phase B",
                        key=REVIEWER_COORDINATOR,
                        text=artifact.text,
                    )

        for lane in REVIEWER_LANES:
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

    def validate_reviewer_task_permissions(
        self,
        artifact: Artifact,
        reviewer_lanes: list[str],
        agents: dict[str, dict[str, Any]],
    ) -> None:
        coordinator = agents.get(REVIEWER_COORDINATOR)
        if coordinator is None:
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR} is required for reviewer task permissions",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )
            return

        if coordinator.get("mcps") != ["gitnexus"]:
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR}.mcps must be exactly ['gitnexus']",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )
        if coordinator.get("skills") != [REVIEWER_COORDINATOR]:
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR}.skills must be exactly ['{REVIEWER_COORDINATOR}']",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )

        permission = coordinator.get("permission")
        if not isinstance(permission, dict):
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR}.permission must be a mapping",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )
            return

        expected_permission = {
            "*": "deny",
            "read": COORDINATOR_READ_PERMISSION,
            **{
                tool: "deny"
                for tool in COORDINATOR_NATIVE_READ_TOOLS[1:]
            },
            **{
                tool: "deny"
                for tool in COORDINATOR_DENIED_TOOLS
                if tool != "read"
            },
            "task": {"*": "deny", **{lane: "allow" for lane in REVIEWER_LANES}},
            "task_status": "allow",
            "task_result": "allow",
        }
        if permission != expected_permission:
            missing = sorted(set(expected_permission) - set(permission))
            extra = sorted(set(permission) - set(expected_permission))
            if missing:
                self.add_error(
                    artifact.path,
                    f"agents.{REVIEWER_COORDINATOR}.permission is missing required entries: {', '.join(missing)}",
                    key=REVIEWER_COORDINATOR,
                    text=artifact.text,
                )
            if extra:
                self.add_error(
                    artifact.path,
                    f"agents.{REVIEWER_COORDINATOR}.permission has unexpected entries: {', '.join(extra)}",
                    key=REVIEWER_COORDINATOR,
                    text=artifact.text,
                )
            for permission_name in sorted(set(expected_permission) & set(permission)):
                if permission[permission_name] != expected_permission[permission_name]:
                    self.add_error(
                        artifact.path,
                        f"agents.{REVIEWER_COORDINATOR}.permission.{permission_name} does not match the least-privilege coordinator contract",
                        key=permission_name,
                        text=artifact.text,
                    )

        task = permission.get("task")
        if not isinstance(task, dict):
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR}.permission.task must be a mapping",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )
            return

        expected = set(REVIEWER_LANES)
        if set(task) != expected | {"*"}:
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR}.permission.task must contain exactly the wildcard and ten specialist lanes",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )
        if task.get("*") != "deny":
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR}.permission.task must deny all targets by default",
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )

        for lane in REVIEWER_LANES:
            if task.get(lane) != "allow":
                self.add_error(
                    artifact.path,
                    f"agents.{REVIEWER_COORDINATOR}.permission.task.{lane} must be exactly 'allow'",
                    key=REVIEWER_COORDINATOR,
                    text=artifact.text,
                )

        wildcard_targets = sorted(
            key
            for key in task
            if isinstance(key, str) and "*" in key and key != "*"
        )
        if wildcard_targets:
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR}.permission.task must not use prefix-wildcard targets: "
                + ", ".join(wildcard_targets),
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )

        extra_allowed = sorted(
            key
            for key, value in task.items()
            if value == "allow"
            and isinstance(key, str)
            and key not in expected
            and key != "*"
        )
        if extra_allowed:
            self.add_error(
                artifact.path,
                f"agents.{REVIEWER_COORDINATOR}.permission.task has extra allowed targets: "
                + ", ".join(extra_allowed),
                key=REVIEWER_COORDINATOR,
                text=artifact.text,
            )

    @staticmethod
    def _body_after_frontmatter(text: str) -> str:
        """Return the text after the closing frontmatter delimiter, or ""."""
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            return ""
        end = next(
            (index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"),
            None,
        )
        if end is None:
            return ""
        return "".join(lines[end + 1 :])

    @staticmethod
    def _normalized_skill_body(text: str) -> str:
        """Remove only blank separator lines between frontmatter and Markdown."""

        body = Validator._body_after_frontmatter(text)
        return re.sub(r"\A(?:[ \t]*\r?\n)+", "", body)

    def validate_review_command(self) -> None:
        paths = [self.root / ".rulesync" / "commands" / "review-pr.md"]
        if self.payload:
            paths.append(self.payload / "commands" / "review-pr.md")

        required_body_markers = (
            "orchestrator",
            "sole coordinator",
            "functions.skill",
            REVIEWER_COORDINATOR,
            *REVIEWER_LANES,
        )
        forbidden_body_markers = ("claudecode", "claude code")
        for path in paths:
            artifact = self._load_frontmatter(path, kind="command")
            if artifact is None:
                continue
            metadata = self.require_mapping(artifact, "command frontmatter")
            if metadata is None:
                continue
            targets = metadata.get("targets")
            if not isinstance(targets, list):
                self.add_error(
                    path,
                    "review-pr command frontmatter targets must be a list",
                    key="targets",
                    text=artifact.text,
                )
                continue
            if targets != ["opencode"]:
                self.add_error(
                    path,
                    "review-pr command frontmatter targets must be exactly "
                    "['opencode']",
                    key="targets",
                    text=artifact.text,
                )

            body = self._body_after_frontmatter(artifact.text)
            normalized_body = body.casefold()
            reviewer_references = set(
                re.findall(r"\breviewer-[a-z0-9][a-z0-9-]*\b", body)
            )
            unknown_reviewer_references = sorted(
                reviewer_id
                for reviewer_id in reviewer_references
                if reviewer_id not in REVIEWER_IDS
            )
            for reviewer_id in unknown_reviewer_references:
                self.add_error(
                    path,
                    f"review-pr command body references unknown reviewer ID {reviewer_id!r}; use the explicit reviewer registry",
                    key=reviewer_id,
                    text=artifact.text,
                )
            for marker in required_body_markers:
                if marker not in normalized_body:
                    self.add_error(
                        path,
                        "review-pr command body is missing OpenCode-only marker "
                        f"{marker!r}",
                        key=marker,
                        text=artifact.text,
                    )
            for marker in forbidden_body_markers:
                if marker in normalized_body:
                    self.add_error(
                        path,
                        f"review-pr command body contains stale Claude marker {marker!r}",
                        key=marker,
                        text=artifact.text,
                    )

    def validate_rulesync_targets(self) -> None:
        """Require the OpenCode-only Rulesync target and output root."""
        path = self.root / "rulesync.jsonc"
        artifact = self.load_json(path, jsonc=True)
        if artifact is None:
            return
        config = self.require_mapping(artifact, "rulesync.jsonc")
        if config is None:
            return

        targets = config.get("targets")
        if not isinstance(targets, list):
            self.add_error(
                path,
                "rulesync.jsonc targets must be a list",
                key="targets",
                text=artifact.text,
            )
        elif targets != ["opencode"]:
            self.add_error(
                path,
                "rulesync.jsonc targets must be exactly ['opencode']",
                key="targets",
                text=artifact.text,
            )

        output_roots = config.get("outputRoots")
        if not isinstance(output_roots, dict):
            self.add_error(
                path,
                "rulesync.jsonc outputRoots must be a mapping",
                key="outputRoots",
                text=artifact.text,
            )
            return
        self.compare_sets(
            path,
            "rulesync.jsonc outputRoots",
            RULESYNC_TARGETS,
            output_roots.keys(),
            text=artifact.text,
        )
        for name, value in output_roots.items():
            if not isinstance(name, str) or not isinstance(value, str):
                self.add_error(
                    path,
                    "rulesync.jsonc outputRoots must map target names to paths",
                    key="outputRoots",
                    text=artifact.text,
                )
                continue
            if name == "opencode" and value != OPENCODE_OUTPUT_ROOT:
                self.add_error(
                    path,
                    "rulesync.jsonc outputRoots.opencode must be "
                    f"{OPENCODE_OUTPUT_ROOT!r}",
                    key="opencode",
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
        self.validate_mcp_transports(mcp_artifact)
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
        source_omo_artifact = (
            self.load_json(self.root / "oh-my-opencode-slim.json")
            if self.payload
            else omo_artifact
        )
        self.validate_opencode_reviewer_routing(omo_artifact)
        self.validate_agent_output_permissions(omo_artifact)
        if self.payload and source_omo_artifact is not None:
            self.validate_opencode_reviewer_routing(source_omo_artifact)
            self.validate_agent_output_permissions(source_omo_artifact)
        agents, omo_mcp_refs, omo_skill_refs = self.collect_omo_agents(omo_artifact)
        self.validate_mcp_references(omo_mcp_refs, server_names, disabled_server_names)
        self.validate_mcp_assignments(omo_artifact, agents)

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
        self.validate_gitnexus_rename_permission(opencode_artifact)
        if self.payload:
            source_opencode_artifact = self.load_json(self.root / "opencode.json")
            self.validate_gitnexus_rename_permission(source_opencode_artifact)
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
        self.validate_fixer_model_contract(
            omo_artifact,
            profiles,
            opencode_artifact,
            model_catalog,
            overview_artifact,
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

        reviewer_lanes: list[str] = list(REVIEWER_LANES)
        reviewer_contracts = []
        reviewer_skill_path = (
            self.root / ".rulesync" / "skills" / REVIEWER_COORDINATOR / "SKILL.md"
        )
        reviewer_skill_text = self.load_required_reviewer_skill(
            reviewer_skill_path,
            f"canonical {REVIEWER_COORDINATOR} skill",
        )
        if reviewer_skill_text is not None:
            reviewer_contracts.append((reviewer_skill_path, reviewer_skill_text))
        canonical_skill_text = reviewer_skill_text
        staged_reviewer_skill_path = None
        if self.payload:
            staged_reviewer_skill_path = (
                self.payload / "skills" / REVIEWER_COORDINATOR / "SKILL.md"
            )
            staged_reviewer_skill_text = self.load_required_reviewer_skill(
                staged_reviewer_skill_path,
                f"staged {REVIEWER_COORDINATOR} skill",
            )
            if staged_reviewer_skill_text is not None:
                reviewer_contracts.append(
                    (staged_reviewer_skill_path, staged_reviewer_skill_text)
                )
            canonical_skill_text = staged_reviewer_skill_text
        self.validate_reviewer_skill_integrity(
            reviewer_skill_path, staged_reviewer_skill_path
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
        self.validate_reviewer_runtime_health(reviewer_contracts)
        self.validate_reviewer_lane_prompts(omo_artifact, reviewer_lanes, agents)
        self.validate_reviewer_task_permissions(omo_artifact, reviewer_lanes, agents)
        self.validate_fixer_scheduler_contract(overview_artifact)
        if self.payload and source_omo_artifact is not None:
            source_agents, _, _ = self.collect_omo_agents(source_omo_artifact)
            self.validate_mcp_assignments(source_omo_artifact, source_agents)
            self.validate_reviewer_task_permissions(
                source_omo_artifact, list(REVIEWER_LANES), source_agents
            )
        self.validate_review_command()
        self.validate_rulesync_targets()

        self.validate_source_subagents(
            set(agents),
            server_names,
            disabled_server_names,
            source_skill_names,
            payload_skill_names,
        )
        if self.payload:
            self.validate_opencode_manifest(
                self.payload / OPENCODE_MANIFEST_NAME,
                self.payload,
                require_present=True,
            )
        if self.opencode_config:
            live_manifest = self.opencode_config / OPENCODE_MANIFEST_NAME
            if live_manifest.exists() or live_manifest.is_symlink():
                self.validate_opencode_manifest(
                    live_manifest,
                    self.opencode_config,
                    require_present=True,
                )
            canonical_skill = (
                self.payload / "skills" / REVIEWER_COORDINATOR / "SKILL.md"
                if self.payload
                else self.root / ".rulesync" / "skills" / REVIEWER_COORDINATOR / "SKILL.md"
            )
            self.validate_reviewer_shadow(
                canonical_skill,
                canonical_skill_text if canonical_skill_text is not None else "",
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

    def validate_gitnexus_rename_permission(self, artifact: Artifact | None) -> None:
        """Require OpenCode to deny GitNexus' exposed rename tool explicitly."""

        if artifact is None:
            return
        config = self.require_mapping(artifact, "opencode.json")
        if config is None:
            return
        permission = config.get("permission")
        if not isinstance(permission, dict):
            self.add_error(
                artifact.path,
                "permission must be a mapping denying gitnexus_rename",
                key="permission",
                text=artifact.text,
            )
            return
        if permission.get("gitnexus_rename") != "deny":
            self.add_error(
                artifact.path,
                "permission.gitnexus_rename must be exactly 'deny'",
                key="gitnexus_rename",
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
    parser.add_argument(
        "--opencode-config",
        type=Path,
        default=None,
        help="live or fixture OpenCode config directory to validate ownership and shadow state",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    validator = Validator(root, args.payload, args.opencode_config)
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
