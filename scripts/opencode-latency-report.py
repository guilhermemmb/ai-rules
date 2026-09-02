#!/usr/bin/env python3
"""Produce a privacy-preserving latency report from an OpenCode SQLite DB.

The reporter intentionally uses only a small allow-list of metadata fields. It
never puts prompt, source, tool argument, tool output, or arbitrary JSON data
in the report. The database is opened through SQLite's read-only URI mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

SCHEMA_VERSION = 1
DEFAULT_DB_RELATIVE_PATHS = (
    Path(".local/share/opencode/opencode.db"),
    Path("Library/Application Support/opencode/opencode.db"),
    Path("Library/Application Support/Opencode/opencode.db"),
    Path(".config/opencode/opencode.db"),
)
TABLE_ALIASES = {
    "session": ("session", "sessions"),
    "message": ("message", "messages"),
    "part": ("part", "parts"),
}
JSON_COLUMNS = ("data",)
ID_COLUMNS = ("id", "session_id", "sessionid", "message_id", "messageid")
SESSION_ID_COLUMNS = ("session_id", "sessionid", "session")
MESSAGE_ID_COLUMNS = ("message_id", "messageid")
TIME_COLUMNS = (
    "time_created",
    "time_updated",
    "time_completed",
    "created_at",
    "updated_at",
    "completed_at",
    "started_at",
    "ended_at",
    "start_time",
    "end_time",
)
AGENT_COLUMNS = ("agent", "agent_id", "agentid")
MODEL_COLUMNS = ("model", "model_id", "modelid")
PROVIDER_COLUMNS = ("provider", "provider_id", "providerid")
ROLE_COLUMNS = ("role",)
TYPE_COLUMNS = ("type", "part_type", "parttype")
TOOL_COLUMNS = ("tool", "tool_name", "toolname")
CALL_ID_COLUMNS = ("call_id", "callid")
STATUS_COLUMNS = ("status",)
TOKEN_COLUMNS = (
    "input_tokens",
    "output_tokens",
    "cache_read",
    "cache_write",
    "cache_read_tokens",
    "cache_write_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "cache_write_input_tokens",
    "reasoning_tokens",
    "total_tokens",
)
RETRY_COLUMNS = ("retry", "retried", "retries", "retry_count", "attempt", "attempts")
FALLBACK_COLUMNS = ("fallback", "fallback_model", "fallbackmodel")
TOKEN_NAMES = ("input", "output", "cache_read", "cache_write")
TOKEN_KEY_ALIASES = {
    "input": ("input", "prompt", "input_tokens", "prompt_tokens"),
    "output": ("output", "completion", "output_tokens", "completion_tokens"),
    "cache_read": (
        "cache_read",
        "cacheRead",
        "cache_read_tokens",
        "cache_read_input_tokens",
        "read",
    ),
    "cache_write": (
        "cache_write",
        "cacheWrite",
        "cache_write_tokens",
        "cache_creation_input_tokens",
        "write",
    ),
}
SAFE_TEXT_LIMIT = 160
SESSION_DISPLAY_LIMIT = 96
_SENSITIVE_VALUE = re.compile(
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer\s+|password|secret|"
    r"-----begin .*private key-----|sk-[a-z0-9][a-z0-9_-]{7,}|"
    r"gh[pousr]_[a-z0-9]{4,}|github_pat_[a-z0-9_]{4,}|"
    r"xox[baprs]-[a-z0-9-]{4,}|(?:akia|asia)[0-9a-z]{8,}|"
    r"(?:sk|rk|pk)_(?:live|test)_[a-z0-9]{4,}|glpat-[a-z0-9-_]{4,}|"
    r"(?:AIza|ya29\.)[a-z0-9._-]{8,}|(?:npm_|pypi-)[a-z0-9._-]{4,})",
    re.IGNORECASE,
)
_EMAIL_VALUE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_ACCOUNT_VALUE = re.compile(
    r"(?:^|[^a-z])(?:account|control[-_ ]?account|credential|user|org|tenant|"
    r"workspace|customer)(?:$|[^a-z])",
    re.IGNORECASE,
)
_DURATION_TOKEN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)(?P<unit>[smhdw])", re.IGNORECASE
)
MIN_EPOCH_SECONDS = -62135596800.0
MAX_EPOCH_SECONDS = 253402300799.999


class WarningCollector:
    """Deduplicated warnings that never contain database values."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.items: list[str] = []

    def add(self, message: str) -> None:
        if message not in self._seen:
            self._seen.add(message)
            self.items.append(message)


def _safe_text(value: Any, limit: int = SAFE_TEXT_LIMIT) -> str | None:
    if not isinstance(value, str):
        return None
    value = "".join(character if character.isprintable() else "?" for character in value)
    value = value.strip()
    if not value or _SENSITIVE_VALUE.search(value):
        return None
    return value[:limit]


def _safe_identifier(value: Any, limit: int = SESSION_DISPLAY_LIMIT) -> str | None:
    """Return a bounded identifier suitable for metadata output."""

    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None
    else:
        text = _safe_text(value, limit * 2)
        if text is None:
            return None
    if _EMAIL_VALUE.fullmatch(text) or _ACCOUNT_VALUE.search(text):
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 13] + "..." + text[-10:]


def _safe_correlation_id(value: Any) -> str | None:
    """Hash a non-account identifier before it can enter report output."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None
    if (
        not text
        or len(text) > SAFE_TEXT_LIMIT * 2
        or _SENSITIVE_VALUE.search(text)
        or _EMAIL_VALUE.fullmatch(text)
        or _ACCOUNT_VALUE.search(text)
        or not re.fullmatch(r"[A-Za-z0-9._:-]+", text)
        or text.lstrip("-").isdigit()
    ):
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
    return f"sha256:{digest}"


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def discover_database_path(explicit_path: Path | None = None) -> Path | None:
    """Find the first conventional OpenCode database path that exists."""

    if explicit_path is not None:
        return explicit_path.expanduser()

    candidates: list[Path] = []
    data_home = Path.home() / ".local" / "share"
    if xdg_data_home := _safe_text(os.environ.get("XDG_DATA_HOME")):
        data_home = Path(xdg_data_home).expanduser()
    candidates.append(data_home / "opencode" / "opencode.db")
    candidates.extend(Path.home() / relative for relative in DEFAULT_DB_RELATIVE_PATHS[1:])
    candidates.append(Path.home() / DEFAULT_DB_RELATIVE_PATHS[0])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def parse_duration(value: str) -> float:
    """Parse a compact duration such as ``24h`` or ``1h30m`` into seconds."""

    text = value.strip()
    if not text:
        raise ValueError("duration must not be empty")
    position = 0
    total = 0.0
    for match in _DURATION_TOKEN.finditer(text):
        if match.start() != position:
            raise ValueError("duration must contain number/unit pairs (for example 24h)")
        number = float(match.group("value"))
        unit = match.group("unit").lower()
        total += number * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
        position = match.end()
    if position != len(text) or total <= 0 or not math.isfinite(total):
        raise ValueError("duration must contain a positive value such as 30m, 24h, or 7d")
    return total


def _timestamp(
    value: Any,
    warnings: WarningCollector | None = None,
    label: str = "timestamp",
) -> float | None:
    def invalid(reason: str) -> None:
        if warnings is not None:
            warnings.add(f"{label} {reason}; affected timing was skipped")

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (OverflowError, ValueError):
            invalid("was outside the supported date range")
            return None
        if not math.isfinite(number):
            invalid("was non-finite")
            return None
        # OpenCode has used milliseconds; tolerate seconds, microseconds, and ns.
        if abs(number) >= 1e17:
            number /= 1e9
        elif abs(number) >= 1e14:
            number /= 1e6
        elif abs(number) >= 1e11:
            number /= 1e3
        if not math.isfinite(number) or not MIN_EPOCH_SECONDS <= number <= MAX_EPOCH_SECONDS:
            invalid("was outside the supported date range")
            return None
        return number
    if isinstance(value, str):
        text = value.strip()
        try:
            return _timestamp(float(text), warnings, label)
        except (OverflowError, ValueError):
            pass
        try:
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            parsed = datetime.fromisoformat(normalized)
        except (OverflowError, ValueError):
            invalid("was invalid")
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        try:
            result = parsed.timestamp()
        except (OverflowError, OSError, ValueError):
            invalid("was outside the supported date range")
            return None
        if not math.isfinite(result) or not MIN_EPOCH_SECONDS <= result <= MAX_EPOCH_SECONDS:
            invalid("was outside the supported date range")
            return None
        return result
    return None


def _iso_timestamp(value: float | None) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(
            value, tz=timezone.utc
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def _number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and math.isfinite(value):
        return int(value) if value >= 0 else None
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        if math.isfinite(parsed) and parsed >= 0:
            return int(parsed)
    return None


def _bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "on"}:
            return True
        if lowered in {"false", "no", "0", "off"}:
            return False
    return None


def _first(mapping: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return None


def _extract_tokens(payload: dict[str, Any]) -> dict[str, int | None]:
    """Extract only the four token counters from known token objects."""

    sources: list[dict[str, Any]] = []
    tokens = payload.get("tokens")
    if isinstance(tokens, dict):
        sources.append(tokens)
    # Some schema versions store counters directly on a step-finish object.
    if any(name in payload for aliases in TOKEN_KEY_ALIASES.values() for name in aliases):
        sources.append(payload)

    result: dict[str, int | None] = {name: None for name in TOKEN_NAMES}
    for source in sources:
        cache = source.get("cache")
        for name, aliases in TOKEN_KEY_ALIASES.items():
            value = _number(_first(source, aliases))
            if value is None and name.startswith("cache_") and isinstance(cache, dict):
                value = _number(_first(cache, aliases))
            if result[name] is None and value is not None:
                result[name] = value
    return result


def _apply_retry_value(metadata: dict[str, Any], key: str, value: Any) -> None:
    metadata["retry_metadata"] = True
    numeric = _number(value)
    if key in {"attempt", "attempts"}:
        if numeric is not None:
            metadata["retry_count"] += max(numeric - 1, 0)
            metadata["retry_signal"] = metadata["retry_signal"] or numeric > 1
        return
    if numeric is not None:
        metadata["retry_count"] += numeric
        metadata["retry_signal"] = metadata["retry_signal"] or numeric > 0
        return
    flag = _bool_value(value)
    if flag:
        metadata["retry_count"] += 1
        metadata["retry_signal"] = True


def _parse_json(raw: Any, label: str, warnings: WarningCollector) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            warnings.add(f"malformed JSON in {label}; affected metadata was skipped")
            return {}
    if not isinstance(raw, str):
        warnings.add(f"malformed JSON in {label}; affected metadata was skipped")
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        warnings.add(f"malformed JSON in {label}; affected metadata was skipped")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _payload_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy allow-listed metadata and discard the payload immediately."""

    metadata: dict[str, Any] = {
        "agent": _safe_identifier(_first(payload, ("agent", "agentID", "agentId"))),
        "model": _safe_identifier(
            _first(payload, ("model", "modelID", "modelId", "model_id"))
        ),
        "provider": _safe_identifier(
            _first(payload, ("provider", "providerID", "providerId", "provider_id"))
        ),
        "role": _safe_text(payload.get("role"), 32),
        "type": _safe_text(_first(payload, ("type", "partType", "part_type")), 32),
        "tool": _safe_identifier(_first(payload, ("tool", "toolName", "tool_name"))),
        "call_id": _safe_identifier(_first(payload, ("callID", "callId", "call_id"))),
        "status": _safe_text(payload.get("status"), 32),
        "tokens": _extract_tokens(payload),
        "retry_count": 0,
        "retry_signal": False,
        "fallback_signal": False,
        "retry_metadata": False,
        "fallback_metadata": False,
    }

    for key in ("retry", "retried", "retries", "retryCount", "retry_count", "attempt", "attempts"):
        if key not in payload:
            continue
        _apply_retry_value(metadata, key, payload[key])

    for key in ("fallback", "fallbackModel", "fallback_model", "fallbackProvider"):
        if key not in payload:
            continue
        metadata["fallback_metadata"] = True
        flag = _bool_value(payload[key])
        metadata["fallback_signal"] = metadata["fallback_signal"] or (
            flag if flag is not None else bool(_safe_text(payload[key], 64))
        )

    for key in ("finish", "finishReason", "finish_reason", "status"):
        text = _safe_text(payload.get(key), 64)
        if text is None:
            continue
        lowered = text.lower()
        if "retry" in lowered:
            metadata["retry_metadata"] = True
            metadata["retry_signal"] = True
        if "fallback" in lowered:
            metadata["fallback_metadata"] = True
            metadata["fallback_signal"] = True

    return metadata


def _nested_time(payload: dict[str, Any], *names: str) -> float | None:
    for name in names:
        candidate = payload.get(name)
        if isinstance(candidate, dict):
            start = _timestamp(_first(candidate, ("start", "started_at", "start_time")))
            if start is not None:
                return start
    return None


def _payload_times(
    payload: dict[str, Any],
    warnings: WarningCollector | None = None,
    label: str = "payload timestamp",
) -> tuple[float | None, float | None, float | None]:
    time = payload.get("time")
    time_map = time if isinstance(time, dict) else {}
    state = payload.get("state")
    state_map = state if isinstance(state, dict) else {}
    state_time = state_map.get("time")
    state_time_map = state_time if isinstance(state_time, dict) else {}
    start = _timestamp(
        _first(
            time_map,
            ("start", "started_at", "start_time", "created", "created_at"),
        ),
        warnings,
        f"{label} start",
    )
    if start is None:
        start = _timestamp(
            _first(state_time_map, ("start", "started_at", "start_time")),
            warnings,
            f"{label} start",
        )
    end = _timestamp(
        _first(
            time_map,
            ("end", "ended_at", "end_time", "completed", "completed_at", "finish"),
        ),
        warnings,
        f"{label} end",
    )
    if end is None:
        end = _timestamp(
            _first(state_time_map, ("end", "ended_at", "end_time")),
            warnings,
            f"{label} end",
        )
    created = _timestamp(
        _first(time_map, ("created", "created_at")),
        warnings,
        f"{label} created",
    )
    return start, end, created


def _column_map(columns: list[str]) -> dict[str, str]:
    return {column.lower(): column for column in columns}


def _actual_column(column_map: dict[str, str], candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        if candidate.lower() in column_map:
            return column_map[candidate.lower()]
    return None


def _row_value(row: dict[str, Any], column_map: dict[str, str], candidates: Iterable[str]) -> Any:
    column = _actual_column(column_map, candidates)
    return row.get(column) if column else None


def _allowed_columns(columns: list[str]) -> list[str]:
    allowed = {
        name.lower()
        for name in (
            *ID_COLUMNS,
            *SESSION_ID_COLUMNS,
            *MESSAGE_ID_COLUMNS,
            *TIME_COLUMNS,
            *AGENT_COLUMNS,
            *MODEL_COLUMNS,
            *PROVIDER_COLUMNS,
            *ROLE_COLUMNS,
            *TYPE_COLUMNS,
            *TOOL_COLUMNS,
            *CALL_ID_COLUMNS,
            *STATUS_COLUMNS,
            *TOKEN_COLUMNS,
            *RETRY_COLUMNS,
            *FALLBACK_COLUMNS,
            *JSON_COLUMNS,
        )
    }
    return [column for column in columns if column.lower() in allowed]


def _read_table(
    connection: sqlite3.Connection,
    table: str,
    columns: list[str],
    warnings: WarningCollector,
) -> list[dict[str, Any]]:
    selected = _allowed_columns(columns)
    if not selected:
        warnings.add(f"table {table} has no supported metadata columns; affected data was skipped")
        return []
    projection = ", ".join(_quote_identifier(column) for column in selected)
    try:
        cursor = connection.execute(f"SELECT {projection} FROM {_quote_identifier(table)}")
        return [dict(zip(selected, row)) for row in cursor.fetchall()]
    except sqlite3.Error:
        warnings.add(f"could not read table {table}; affected data was skipped")
        return []


def _inspect_schema(connection: sqlite3.Connection, warnings: WarningCollector) -> dict[str, list[str]]:
    try:
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    except sqlite3.Error:
        warnings.add("could not inspect SQLite schema; report contains no database rows")
        return {}

    schema: dict[str, list[str]] = {}
    for (table_name,) in table_rows:
        if not isinstance(table_name, str):
            continue
        try:
            rows = connection.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
        except sqlite3.Error:
            warnings.add(f"could not inspect columns for table {table_name}")
            continue
        schema[table_name] = [row[1] for row in rows if len(row) > 1 and isinstance(row[1], str)]
    return schema


def _find_table(schema: dict[str, list[str]], logical_name: str) -> str | None:
    aliases = {name.lower() for name in TABLE_ALIASES[logical_name]}
    for table in schema:
        if table.lower() in aliases:
            return table
    return None


def _warn_missing_table_or_columns(
    schema: dict[str, list[str]],
    logical_name: str,
    table: str | None,
    required_columns: tuple[str, ...],
    warnings: WarningCollector,
) -> None:
    if table is None:
        warnings.add(f"{logical_name} table not found; {logical_name} metadata is unavailable")
        return
    column_map = _column_map(schema[table])
    if not _actual_column(column_map, required_columns):
        warnings.add(f"{table} is missing its {logical_name} identifier column; some metadata is unavailable")


def _warn_missing_column(
    schema: dict[str, list[str]],
    table: str | None,
    candidates: tuple[str, ...],
    message: str,
    warnings: WarningCollector,
) -> None:
    if table is not None and not _actual_column(_column_map(schema[table]), candidates):
        warnings.add(message)


def _warn_missing_part_association(
    schema: dict[str, list[str]],
    table: str | None,
    warnings: WarningCollector,
) -> None:
    if table is None:
        warnings.add("part table not found; part metadata is unavailable")
        return
    columns = _column_map(schema[table])
    has_session_link = _actual_column(columns, SESSION_ID_COLUMNS) is not None
    has_message_link = _actual_column(columns, MESSAGE_ID_COLUMNS) is not None
    if not has_session_link and not has_message_link:
        warnings.add(
            f"{table} is missing session_id and message_id linkage; part metadata was skipped"
        )


def _valid_interval(start: float | None, end: float | None) -> bool:
    return (
        start is not None
        and end is not None
        and math.isfinite(start)
        and math.isfinite(end)
        and end >= start
    )


@dataclass
class SessionAggregate:
    session_id: str
    start: float | None = None
    end: float | None = None
    agents: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    providers: set[str] = field(default_factory=set)
    tokens: dict[str, int | None] = field(
        default_factory=lambda: {name: None for name in TOKEN_NAMES}
    )
    token_records: int = 0
    message_records: int = 0
    model_intervals: list[tuple[float, float]] = field(default_factory=list)
    user_turns: list[float] = field(default_factory=list)
    assistant_output_times: list[float] = field(default_factory=list)
    tool_count: int = 0
    tool_duration_ms: int = 0
    tool_unknown_durations: int = 0
    tool_names: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    mcp_count: int = 0
    mcp_duration_ms: int = 0
    mcp_unknown_durations: int = 0
    mcp_names: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    retry_count: int = 0
    retry_signal: bool = False
    fallback_signal: bool = False
    retry_metadata: bool = False
    fallback_metadata: bool = False
    tool_intervals: list[tuple[float, float]] = field(default_factory=list)
    message_token_metrics: set[str] = field(default_factory=set)
    unknowns: set[str] = field(default_factory=set)

    def update_window(self, start: float | None, end: float | None) -> None:
        if start is not None and end is not None and not _valid_interval(start, end):
            return
        if start is not None:
            self.start = start if self.start is None else min(self.start, start)
        if end is not None:
            self.end = end if self.end is None else max(self.end, end)

    def update_metadata(self, metadata: dict[str, Any]) -> None:
        for field_name, target in (("agent", self.agents), ("model", self.models), ("provider", self.providers)):
            value = metadata.get(field_name)
            if isinstance(value, str):
                target.add(value)
        self.retry_count += int(metadata.get("retry_count", 0))
        self.retry_signal = self.retry_signal or bool(metadata.get("retry_signal"))
        self.fallback_signal = self.fallback_signal or bool(metadata.get("fallback_signal"))
        self.retry_metadata = self.retry_metadata or bool(metadata.get("retry_metadata"))
        self.fallback_metadata = self.fallback_metadata or bool(metadata.get("fallback_metadata"))

    def add_tokens(self, values: dict[str, int | None], source: str) -> None:
        found = False
        for name in TOKEN_NAMES:
            value = values.get(name)
            if value is None:
                continue
            if source == "message":
                self.message_token_metrics.add(name)
            elif name in self.message_token_metrics:
                # A message counter is authoritative for that metric, while
                # part counters for other metrics are still merged below.
                continue
            found = True
            self.tokens[name] = (self.tokens[name] or 0) + value
        if found:
            self.token_records += 1


def _session_id(row: dict[str, Any], column_map: dict[str, str]) -> str | None:
    value = _row_value(row, column_map, ("id", "session_id", "sessionid"))
    return _safe_correlation_id(value)


def _record_metadata(
    row: dict[str, Any],
    column_map: dict[str, str],
    payload: dict[str, Any],
    warnings: WarningCollector | None = None,
    label: str = "row",
) -> tuple[dict[str, Any], float | None, float | None, float | None]:
    metadata = _payload_metadata(payload)
    scalar_aliases = (
        ("agent", AGENT_COLUMNS),
        ("model", MODEL_COLUMNS),
        ("provider", PROVIDER_COLUMNS),
        ("role", ROLE_COLUMNS),
        ("type", TYPE_COLUMNS),
        ("tool", TOOL_COLUMNS),
        ("call_id", CALL_ID_COLUMNS),
        ("status", STATUS_COLUMNS),
    )
    for name, aliases in scalar_aliases:
        scalar = _safe_identifier(_row_value(row, column_map, aliases)) if name not in {"role", "type", "status"} else _safe_text(_row_value(row, column_map, aliases), 64)
        if scalar is not None and metadata.get(name) is None:
            metadata[name] = scalar

    scalar_tokens: dict[str, int | None] = {name: None for name in TOKEN_NAMES}
    for name, aliases in (
        ("input", ("input_tokens",)),
        ("output", ("output_tokens",)),
        ("cache_read", ("cache_read", "cache_read_tokens", "cache_read_input_tokens")),
        ("cache_write", ("cache_write", "cache_write_tokens", "cache_write_input_tokens", "cache_creation_input_tokens")),
    ):
        scalar_tokens[name] = _number(_row_value(row, column_map, aliases))
    payload_tokens = metadata["tokens"]
    metadata["tokens"] = {
        name: scalar_tokens[name] if scalar_tokens[name] is not None else payload_tokens[name]
        for name in TOKEN_NAMES
    }

    for key, aliases in (("retry", RETRY_COLUMNS), ("fallback", FALLBACK_COLUMNS)):
        scalar_value = _row_value(row, column_map, aliases)
        if scalar_value is None:
            continue
        metadata["retry_metadata" if key == "retry" else "fallback_metadata"] = True
        if key == "retry":
            scalar_column = _actual_column(column_map, aliases)
            _apply_retry_value(
                metadata, (scalar_column or "retry").lower(), scalar_value
            )
        else:
            flag = _bool_value(scalar_value)
            metadata["fallback_signal"] = metadata["fallback_signal"] or (
                flag if flag is not None else bool(_safe_text(scalar_value, 64))
            )

    start, end, created = _payload_times(payload, warnings, f"{label} start/end")
    scalar_start = _timestamp(
        _row_value(row, column_map, ("started_at", "start_time", "time_created", "created_at")),
        warnings,
        f"{label} start",
    )
    scalar_end = _timestamp(
        _row_value(row, column_map, ("ended_at", "end_time", "time_completed", "time_updated", "updated_at", "completed_at")),
        warnings,
        f"{label} end",
    )
    scalar_created = _timestamp(
        _row_value(row, column_map, ("time_created", "created_at")),
        warnings,
        f"{label} created",
    )
    start = start if start is not None else scalar_start
    end = end if end is not None else scalar_end
    created = created if created is not None else scalar_created
    return metadata, start, end, created


def _ensure_session(sessions: dict[str, SessionAggregate], session_id: str) -> SessionAggregate:
    if session_id not in sessions:
        sessions[session_id] = SessionAggregate(session_id)
    return sessions[session_id]


def _is_tool(metadata: dict[str, Any]) -> bool:
    type_name = (metadata.get("type") or "").lower()
    return type_name == "tool" or isinstance(metadata.get("tool"), str)


def _is_mcp(metadata: dict[str, Any]) -> bool:
    tool = (metadata.get("tool") or "").lower()
    type_name = (metadata.get("type") or "").lower()
    return type_name == "mcp" or tool.startswith(("mcp__", "mcp:", "mcp/"))


def _duration_ms(start: float | None, end: float | None) -> int | None:
    if (
        start is None
        or end is None
        or not math.isfinite(start)
        or not math.isfinite(end)
        or end < start
    ):
        return None
    duration = (end - start) * 1000
    return round(duration) if math.isfinite(duration) and duration >= 0 else None


def _union_duration_ms(intervals: list[tuple[float, float]]) -> int | None:
    valid_intervals = [
        (start, end)
        for start, end in intervals
        if _valid_interval(start, end)
    ]
    if not valid_intervals:
        return None
    ordered = sorted(valid_intervals)
    total = 0.0
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end
    total += current_end - current_start
    return round(total * 1000)


def _interval_concurrency(intervals: list[tuple[float, float]]) -> tuple[int | None, int | None, int]:
    valid_intervals = [
        (start, end)
        for start, end in intervals
        if _valid_interval(start, end)
    ]
    if not valid_intervals:
        return None, None, 0
    events: list[tuple[float, int]] = []
    for start, end in valid_intervals:
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda event: (event[0], event[1]))
    current = 0
    maximum = 0
    overlap_seconds = 0.0
    previous: float | None = None
    for timestamp, change in events:
        if previous is not None and current > 1:
            overlap_seconds += timestamp - previous
        current += change
        maximum = max(maximum, current)
        previous = timestamp
    return maximum, round(overlap_seconds * 1000), len(valid_intervals)


def _pair_overlap_ms(intervals: list[tuple[float, float]]) -> tuple[int, int]:
    intervals = [
        (start, end)
        for start, end in intervals
        if _valid_interval(start, end)
    ]
    pairs = 0
    total = 0
    for index, (left_start, left_end) in enumerate(intervals):
        for right_start, right_end in intervals[index + 1 :]:
            overlap = min(left_end, right_end) - max(left_start, right_start)
            if overlap > 0:
                pairs += 1
                total += round(overlap * 1000)
    return pairs, total


def _percentile(values: list[int], percentile: float) -> int | None:
    valid_values = [value for value in values if isinstance(value, int) and value >= 0]
    if not valid_values:
        return None
    ordered = sorted(valid_values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower))


def _ttft_ms(session: SessionAggregate) -> int | None:
    """Find the first assistant output after the first user turn it follows."""

    user_turns = sorted(
        timestamp
        for timestamp in session.user_turns
        if math.isfinite(timestamp)
    )
    outputs = sorted(
        timestamp
        for timestamp in session.assistant_output_times
        if math.isfinite(timestamp)
    )
    for user_turn in user_turns:
        response = next((timestamp for timestamp in outputs if timestamp >= user_turn), None)
        if response is not None:
            duration = (response - user_turn) * 1000
            if math.isfinite(duration) and duration >= 0:
                return round(duration)
    return None


def _event_anchor(
    start: float | None, end: float | None, created: float | None
) -> float | None:
    if start is not None and end is not None:
        if not _valid_interval(start, end):
            return created
        return end
    if created is not None:
        return created
    if end is not None:
        return end
    return start


def _serialize_session(
    session: SessionAggregate, all_sessions: list[SessionAggregate]
) -> dict[str, Any]:
    wall_duration = _duration_ms(session.start, session.end)
    model_duration = _union_duration_ms(session.model_intervals)
    ttft = _ttft_ms(session)
    overlaps = 0
    max_concurrent: int | None = None
    session_start = session.start
    session_end = session.end
    if session_start is not None and session_end is not None:
        others = [
            (item.start, item.end)
            for item in all_sessions
            if item is not session
            and item.start is not None
            and item.end is not None
            and item.end >= item.start
        ]
        overlaps = sum(
            1
            for other_start, other_end in others
            if other_start is not None
            and other_end is not None
            and min(session_end, other_end) - max(session_start, other_start) > 0
        )
        related = [(session_start, session_end), *others]
        max_concurrent, _, _ = _interval_concurrency(related)

    unknowns = set(session.unknowns)
    if wall_duration is None:
        unknowns.add("session start/end wall duration unavailable")
    if model_duration is None:
        unknowns.add("model duration unavailable; model timing is approximate when present")
    if ttft is None:
        unknowns.add(
            "TTFT unavailable; no assistant output was found after a user turn"
        )
    if not session.agents:
        unknowns.add("agent identifier unavailable")
    if not session.models:
        unknowns.add("model identifier unavailable")
    for name, label in (
        ("input", "input tokens"),
        ("output", "output tokens"),
        ("cache_read", "cache-read tokens"),
        ("cache_write", "cache-write tokens"),
    ):
        if session.tokens[name] is None:
            unknowns.add(f"{label} unavailable")
    if session.tool_unknown_durations:
        unknowns.add(f"duration unavailable for {session.tool_unknown_durations} tool event(s)")
    if session.mcp_unknown_durations:
        unknowns.add(f"duration unavailable for {session.mcp_unknown_durations} MCP event(s)")
    if session.message_records and not session.retry_metadata:
        unknowns.add("retry/fallback metadata was not present")

    return {
        "session_id": session.session_id,
        "start": _iso_timestamp(session.start),
        "end": _iso_timestamp(session.end),
        "wall_duration_ms": wall_duration,
        "agents": sorted(session.agents),
        "models": sorted(session.models),
        "providers": sorted(session.providers),
        "tokens": dict(session.tokens),
        "timing": {
            "model_duration_ms_approx": model_duration,
            "ttft_ms_approx": ttft,
            "note": "model duration and TTFT are best-effort approximations from local timestamps",
        },
        "tools": {
            "count": session.tool_count,
            "duration_ms_approx": session.tool_duration_ms if session.tool_count else 0,
            "by_name": dict(sorted(session.tool_names.items())),
        },
        "mcp": {
            "count": session.mcp_count,
            "duration_ms_approx": session.mcp_duration_ms if session.mcp_count else 0,
            "by_name": dict(sorted(session.mcp_names.items())),
        },
        "retry_fallback": {
            "retry_count": session.retry_count if session.message_records else None,
            "retry_detected": session.retry_signal if session.message_records else None,
            "fallback_detected": session.fallback_signal if session.message_records else None,
        },
        "concurrency": {
            "overlaps_other_sessions": overlaps,
            "max_concurrent_sessions": max_concurrent,
        },
        "unknowns": sorted(unknowns),
    }


def _aggregate_tokens(sessions: list[SessionAggregate]) -> dict[str, int | None]:
    result: dict[str, int | None] = {name: None for name in TOKEN_NAMES}
    for session in sessions:
        for name in TOKEN_NAMES:
            value = session.tokens[name]
            if value is not None:
                result[name] = (result[name] or 0) + value
    return result


def generate_report(
    database_path: Path,
    *,
    since: str | None = None,
    session_id: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Read a database in read-only mode and return a JSON-serializable report."""

    warnings = WarningCollector()
    database_path = database_path.expanduser()
    since_seconds = parse_duration(since) if since else None
    cutoff = (datetime.now(tz=timezone.utc).timestamp() if now is None else now) - since_seconds if since_seconds else None
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "database": {"filename": database_path.name, "read_only": True},
        "filters": {"since": since, "session": _safe_correlation_id(session_id)},
        "sessions": [],
        "aggregate": {},
        "unknowns": [],
        "warnings": warnings.items,
    }

    if not database_path.is_file():
        warnings.add("database file was not found; no session data was available")
        report["unknowns"] = ["database path is unknown or unavailable"]
        return report

    uri = "file:" + quote(str(database_path.resolve()), safe="/:\\") + "?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        warnings.add("database could not be opened in read-only mode; no session data was available")
        report["unknowns"] = ["database could not be opened"]
        return report

    try:
        schema = _inspect_schema(connection, warnings)
        table_names = {logical: _find_table(schema, logical) for logical in TABLE_ALIASES}
        _warn_missing_table_or_columns(
            schema, "session", table_names["session"], ("id", "session_id"), warnings
        )
        _warn_missing_table_or_columns(schema, "message", table_names["message"], ("id", "session_id"), warnings)
        _warn_missing_part_association(schema, table_names["part"], warnings)
        _warn_missing_column(
            schema,
            table_names["session"],
            TIME_COLUMNS,
            "session table is missing timestamp columns; session windows may be unknown",
            warnings,
        )
        _warn_missing_column(
            schema,
            table_names["message"],
            JSON_COLUMNS,
            "message table is missing its JSON data column; message metadata is unavailable",
            warnings,
        )
        _warn_missing_column(
            schema,
            table_names["part"],
            JSON_COLUMNS,
            "part table is missing its JSON data column; part metadata is unavailable",
            warnings,
        )

        sessions: dict[str, SessionAggregate] = {}
        message_roles: dict[tuple[str, str], str] = {}
        message_sessions: dict[str, str] = {}
        session_rows = (
            _read_table(connection, table_names["session"], schema[table_names["session"]], warnings)
            if table_names["session"]
            else []
        )
        if table_names["session"]:
            session_columns = _column_map(schema[table_names["session"]])
            for index, row in enumerate(session_rows, 1):
                identifier = _session_id(row, session_columns)
                if identifier is None:
                    warnings.add("a session row had no usable identifier; that row was skipped")
                    continue
                session = _ensure_session(sessions, identifier)
                start = _timestamp(
                    _row_value(row, session_columns, ("time_created", "created_at", "started_at")),
                    warnings,
                    f"{table_names['session']} row {index} start",
                )
                end = _timestamp(
                    _row_value(row, session_columns, ("time_updated", "updated_at", "time_completed", "completed_at", "ended_at")),
                    warnings,
                    f"{table_names['session']} row {index} end",
                )
                if start is not None and end is not None and not _valid_interval(start, end):
                    warnings.add(
                        f"{table_names['session']} row {index} has a reversed time interval; timing was skipped"
                    )
                session.update_window(start, end)
                session.update_metadata(_payload_metadata({
                    "agent": _row_value(row, session_columns, AGENT_COLUMNS),
                    "model": _row_value(row, session_columns, MODEL_COLUMNS),
                    "provider": _row_value(row, session_columns, PROVIDER_COLUMNS),
                }))

        message_rows = (
            _read_table(connection, table_names["message"], schema[table_names["message"]], warnings)
            if table_names["message"]
            else []
        )
        if table_names["message"]:
            message_columns = _column_map(schema[table_names["message"]])
            if not _actual_column(message_columns, SESSION_ID_COLUMNS):
                warnings.add(f"{table_names['message']} is missing session linkage; message metadata was skipped")
            else:
                for index, row in enumerate(message_rows, 1):
                    identifier = _safe_correlation_id(
                        _row_value(row, message_columns, SESSION_ID_COLUMNS)
                    )
                    if identifier is None:
                        warnings.add("a message row had no usable session identifier; that row was skipped")
                        continue
                    payload = _parse_json(
                        _row_value(row, message_columns, JSON_COLUMNS),
                        f"{table_names['message']}.data row {index}",
                        warnings,
                    )
                    metadata, start, end, created = _record_metadata(
                        row,
                        message_columns,
                        payload,
                        warnings,
                        f"{table_names['message']}.data row {index}",
                    )
                    session = _ensure_session(sessions, identifier)
                    session.message_records += 1
                    session.update_window(start, end)
                    session.update_metadata(metadata)
                    token_values = metadata["tokens"]
                    if any(value is not None for value in token_values.values()):
                        session.add_tokens(token_values, "message")
                    message_id = _safe_correlation_id(
                        _row_value(row, message_columns, ("id", "message_id", "messageid"))
                    )
                    role = (metadata.get("role") or "").lower()
                    if message_id is not None:
                        message_sessions[message_id] = identifier
                        if role:
                            message_roles[(identifier, message_id)] = role
                    if role == "user":
                        anchor = _event_anchor(start, end, created)
                        if anchor is not None:
                            session.user_turns.append(anchor)
                    elif role == "assistant":
                        if start is not None and end is not None and not _valid_interval(start, end):
                            warnings.add(
                                f"{table_names['message']}.data row {index} has a reversed model interval; timing was skipped"
                            )
                            session.unknowns.add(
                                "reversed or non-finite model time interval ignored"
                            )
                        elif created is not None or start is not None:
                            candidate = start if start is not None else created
                            if candidate is not None:
                                session.assistant_output_times.append(candidate)
                        if (
                            start is not None
                            and end is not None
                            and _valid_interval(start, end)
                        ):
                            session.model_intervals.append((start, end))

        part_rows = (
            _read_table(connection, table_names["part"], schema[table_names["part"]], warnings)
            if table_names["part"]
            else []
        )
        if table_names["part"]:
            part_columns = _column_map(schema[table_names["part"]])
            part_session_column = _actual_column(part_columns, SESSION_ID_COLUMNS)
            part_message_column = _actual_column(part_columns, MESSAGE_ID_COLUMNS)
            if part_session_column is None and part_message_column is None:
                warnings.add(
                    f"{table_names['part']} is missing session_id and message_id linkage; part metadata was skipped"
                )
            else:
                for index, row in enumerate(part_rows, 1):
                    part_message_id = _safe_correlation_id(
                        _row_value(row, part_columns, MESSAGE_ID_COLUMNS)
                    )
                    identifier = _safe_correlation_id(
                        _row_value(row, part_columns, SESSION_ID_COLUMNS)
                    )
                    if identifier is None and part_message_id is not None:
                        identifier = message_sessions.get(part_message_id)
                    if identifier is None:
                        warnings.add(
                            f"{table_names['part']} row {index} could not resolve a safe session through session_id or message_id; row was skipped"
                        )
                        continue
                    payload = _parse_json(
                        _row_value(row, part_columns, JSON_COLUMNS),
                        f"{table_names['part']}.data row {index}",
                        warnings,
                    )
                    metadata, start, end, created = _record_metadata(
                        row,
                        part_columns,
                        payload,
                        warnings,
                        f"{table_names['part']}.data row {index}",
                    )
                    session = _ensure_session(sessions, identifier)
                    session.update_window(start, end)
                    session.update_metadata(metadata)
                    part_type = (metadata.get("type") or "").lower()
                    part_role = metadata.get("role")
                    if not isinstance(part_role, str) or not part_role:
                        part_role = message_roles.get((identifier, part_message_id or ""), "")
                    if part_role == "user":
                        anchor = _event_anchor(start, end, created)
                        if anchor is not None:
                            session.user_turns.append(anchor)
                    elif part_role == "assistant" and part_type in {
                        "text",
                        "reasoning",
                        "tool",
                        "step-finish",
                        "patch",
                    }:
                        if start is not None and end is not None and not _valid_interval(start, end):
                            warnings.add(
                                f"{table_names['part']}.data row {index} has a reversed assistant output interval; timing was skipped"
                            )
                            session.unknowns.add(
                                "reversed or non-finite assistant output interval ignored"
                            )
                        elif created is not None or start is not None:
                            candidate = start if start is not None else created
                            if candidate is not None:
                                session.assistant_output_times.append(candidate)
                    session.add_tokens(metadata["tokens"], "part")
                    if _is_tool(metadata):
                        session.tool_count += 1
                        tool_name = metadata.get("tool") or "unknown"
                        session.tool_names[str(tool_name)] += 1
                        duration = _duration_ms(start, end)
                        if duration is None:
                            session.tool_unknown_durations += 1
                            if start is not None and end is not None:
                                warnings.add(
                                    f"{table_names['part']}.data row {index} has an invalid tool interval; duration was skipped"
                                )
                        elif start is not None and end is not None:
                            session.tool_duration_ms += duration
                            session.tool_intervals.append((start, end))
                        if _is_mcp(metadata):
                            session.mcp_count += 1
                            session.mcp_names[str(tool_name)] += 1
                            if duration is None:
                                session.mcp_unknown_durations += 1
                            elif start is not None and end is not None:
                                session.mcp_duration_ms += duration

        if not table_names["session"] and not sessions:
            warnings.add("no session, message, or part rows were available")

        session_filter = _safe_correlation_id(session_id)
        if session_id is not None and session_filter is None:
            warnings.add("session filter was not a safe correlation ID; no sessions matched")
        selected_sessions: list[SessionAggregate] = []
        for session in sorted(sessions.values(), key=lambda item: (item.start is None, item.start or 0, item.session_id)):
            if session_id is not None and session.session_id != session_filter:
                continue
            if cutoff is not None and session.end is not None and session.end < cutoff:
                continue
            if cutoff is not None and session.start is None and session.end is None:
                session.unknowns.add("since filter could not evaluate this session window")
            selected_sessions.append(session)

        intervals: list[tuple[float, float]] = []
        for session in selected_sessions:
            if (
                session.start is not None
                and session.end is not None
                and _valid_interval(session.start, session.end)
            ):
                intervals.append((session.start, session.end))
        serialized_sessions = [_serialize_session(session, selected_sessions) for session in selected_sessions]
        if any(_ttft_ms(session) is None for session in selected_sessions):
            warnings.add(
                "TTFT unavailable for one or more sessions; approximate output timing was not recorded"
            )
        wall_values = [value for value in (_duration_ms(item.start, item.end) for item in selected_sessions) if value is not None]
        model_values = [value for value in (_union_duration_ms(item.model_intervals) for item in selected_sessions) if value is not None]
        ttft_values = [value for value in (_ttft_ms(item) for item in selected_sessions) if value is not None]
        max_concurrent, overlap_ms, _ = _interval_concurrency(intervals)
        overlap_pairs, pair_overlap_ms = _pair_overlap_ms(intervals)
        tool_intervals = [interval for item in selected_sessions for interval in item.tool_intervals]
        tool_max_concurrent, tool_overlap_ms, _ = _interval_concurrency(tool_intervals)
        report["sessions"] = serialized_sessions
        report["aggregate"] = {
            "session_count": len(selected_sessions),
            "latency_ms": {
                "wall": {"count": len(wall_values), "p50": _percentile(wall_values, 0.50), "p95": _percentile(wall_values, 0.95)},
                "model_approx": {"count": len(model_values), "p50": _percentile(model_values, 0.50), "p95": _percentile(model_values, 0.95)},
                "ttft_approx": {"count": len(ttft_values), "p50": _percentile(ttft_values, 0.50), "p95": _percentile(ttft_values, 0.95)},
            },
            "tokens": _aggregate_tokens(selected_sessions),
            "tools": {
                "count": sum(item.tool_count for item in selected_sessions),
                "duration_ms_approx": sum(item.tool_duration_ms for item in selected_sessions),
                "overlap_duration_ms_approx": tool_overlap_ms,
                "max_concurrent": tool_max_concurrent,
            },
            "mcp": {
                "count": sum(item.mcp_count for item in selected_sessions),
                "duration_ms_approx": sum(item.mcp_duration_ms for item in selected_sessions),
            },
            "concurrency": {
                "max_concurrent_sessions": max_concurrent,
                "overlap_duration_ms_approx": overlap_ms,
                "overlapping_session_pairs": overlap_pairs,
                "pairwise_overlap_duration_ms_approx": pair_overlap_ms,
            },
        }
        if not selected_sessions:
            report["unknowns"] = ["no sessions matched the supplied filters"]
    finally:
        connection.close()

    report["warnings"] = warnings.items
    return report


def _human_report(report: dict[str, Any]) -> str:
    lines = [
        "OpenCode latency report",
        f"Database: {report['database']['filename']} (read-only)",
        f"Sessions: {report['aggregate'].get('session_count', 0)}",
    ]
    latency = report["aggregate"].get("latency_ms", {})
    wall = latency.get("wall", {})
    lines.append(f"Wall duration p50/p95: {wall.get('p50', 'unknown')} / {wall.get('p95', 'unknown')} ms")
    for session in report["sessions"]:
        lines.extend(
            [
                "",
                f"Session {session.get('session_id') or '<unknown>'}: {session.get('start') or '?'} → {session.get('end') or '?'}",
                f"  wall={session.get('wall_duration_ms', 'unknown')} ms; agents={', '.join(session['agents']) or 'unknown'}; models={', '.join(session['models']) or 'unknown'}",
                f"  tokens input/output/cache-read/cache-write={session['tokens']['input']}/{session['tokens']['output']}/{session['tokens']['cache_read']}/{session['tokens']['cache_write']}",
                f"  timing model≈{session['timing']['model_duration_ms_approx']} ms; TTFT≈{session['timing']['ttft_ms_approx']} ms",
                f"  tools={session['tools']['count']} ({session['tools']['duration_ms_approx']} ms); MCP={session['mcp']['count']} ({session['mcp']['duration_ms_approx']} ms)",
                f"  retry/fallback={session['retry_fallback']['retry_detected']}/{session['retry_fallback']['fallback_detected']}; overlaps={session['concurrency']['overlaps_other_sessions']}",
            ]
        )
        if session["unknowns"]:
            lines.append("  unknowns: " + "; ".join(session["unknowns"]))
    if report["unknowns"]:
        lines.append("\nUnknowns: " + "; ".join(report["unknowns"]))
    if report["warnings"]:
        lines.append("\nWarnings:")
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="OpenCode SQLite database path")
    parser.add_argument("--since", help="only include sessions newer than a duration such as 24h or 7d")
    parser.add_argument("--session", dest="session_id", help="only include one session ID")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    if args.since:
        try:
            parse_duration(args.since)
        except ValueError as error:
            parser.error(str(error))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database_path = discover_database_path(args.db)
    if database_path is None:
        database_path = Path("opencode.db")
    try:
        report = generate_report(
            database_path,
            since=args.since,
            session_id=args.session_id,
        )
    except (OSError, ValueError) as error:
        # CLI input errors are not database warnings; do not print values from a DB.
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_human_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
