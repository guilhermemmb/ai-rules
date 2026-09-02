#!/usr/bin/env bash

set -eo pipefail

if [[ -z "${AI_RULES_ZSH_BOOTSTRAPPED:-}" ]]; then
  exec zsh -lc 'source "$HOME/.zshrc"; export AI_RULES_ZSH_BOOTSTRAPPED=1; exec bash "$1" "$2"' -- "$0" "${1:-}"
fi
set -u

usage() {
  printf '%s\n' \
    'Usage: smoke-opencode-reviewer-runtime.sh --run' \
    '' \
    'This opt-in command starts a fresh, read-only OpenCode runtime smoke test.'
}

if [[ "${1:-}" != "--run" || $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

export REVIEWER_MAX_PARALLEL=1
export OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"

if ! command -v opencode >/dev/null 2>&1; then
  printf 'FAILED: opencode is not available on PATH\n' >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf 'FAILED: python3 is required for read-only session inspection\n' >&2
  exit 1
fi

ACTIVE_CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
ACTIVE_OMO_PATH="$ACTIVE_CONFIG_DIR/oh-my-opencode-slim.json"
ACTIVE_REVIEWER_SKILL_PATH="$ACTIVE_CONFIG_DIR/skills/reviewer/SKILL.md"
SOURCE_OMO_PATH="$REPO_ROOT/oh-my-opencode-slim.json"
SOURCE_REVIEWER_SKILL_PATH="$REPO_ROOT/.rulesync/skills/reviewer/SKILL.md"
if ! python3 - "$ACTIVE_OMO_PATH" "$ACTIVE_REVIEWER_SKILL_PATH" "$SOURCE_OMO_PATH" "$SOURCE_REVIEWER_SKILL_PATH" <<'PY'
import json
import sys
from pathlib import Path

omo_path = Path(sys.argv[1])
skill_path = Path(sys.argv[2])
source_omo_path = Path(sys.argv[3])
source_skill_path = Path(sys.argv[4])
try:
    config = json.loads(omo_path.read_text(encoding="utf-8"))
    skill_text = skill_path.read_text(encoding="utf-8")
    source_config = json.loads(source_omo_path.read_text(encoding="utf-8"))
    source_skill_text = source_skill_path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
    print(f"active OpenCode reviewer configuration is unavailable: {error}", file=sys.stderr)
    raise SystemExit(1)

preset_name = config.get("preset", "bifrost")
orchestrator = config.get("presets", {}).get(preset_name, {}).get("orchestrator", {})
source_preset_name = source_config.get("preset", "bifrost")
source_orchestrator = source_config.get("presets", {}).get(source_preset_name, {}).get("orchestrator", {})
required_lanes = {
    "reviewer-accessibility",
    "reviewer-code",
    "reviewer-comments",
    "reviewer-data-integrity",
    "reviewer-errors",
    "reviewer-performance",
    "reviewer-security",
    "reviewer-simplifier",
    "reviewer-test",
    "reviewer-types",
}
agents = config.get("agents", {})
missing = sorted(required_lanes - set(agents))
if preset_name != source_preset_name:
    print("active OpenCode preset differs from Rulesync source", file=sys.stderr)
    raise SystemExit(1)
if orchestrator.get("skills") != source_orchestrator.get("skills"):
    print("active OpenCode orchestrator skills differ from Rulesync source", file=sys.stderr)
    raise SystemExit(1)
if "reviewer" not in orchestrator.get("skills", []):
    print("active OpenCode orchestrator does not preload reviewer", file=sys.stderr)
    raise SystemExit(1)
if set(agents) != set(source_config.get("agents", {})):
    print("active OpenCode agent definitions differ from Rulesync source", file=sys.stderr)
    raise SystemExit(1)
def comparable_agent(value: object) -> object:
    return value

if comparable_agent(orchestrator) != comparable_agent(source_orchestrator):
    print("active OpenCode orchestrator definition differs from Rulesync source", file=sys.stderr)
    raise SystemExit(1)

source_agents = source_config.get("agents", {})
for agent_name in sorted(set(agents) | set(source_agents)):
    if comparable_agent(agents.get(agent_name)) != comparable_agent(source_agents.get(agent_name)):
        print(
            f"active OpenCode agent definition differs from Rulesync source: {agent_name}",
            file=sys.stderr,
        )
        raise SystemExit(1)
active_preset_agents = config.get("presets", {}).get(preset_name, {})
source_preset_agents = source_config.get("presets", {}).get(source_preset_name, {})
if set(active_preset_agents) != set(source_preset_agents):
    print("active OpenCode preset agents differ from Rulesync source", file=sys.stderr)
    raise SystemExit(1)
for agent_name in sorted(set(active_preset_agents) | set(source_preset_agents)):
    if comparable_agent(active_preset_agents.get(agent_name)) != comparable_agent(source_preset_agents.get(agent_name)):
        print(
            f"active OpenCode preset agent differs from Rulesync source: {agent_name}",
            file=sys.stderr,
        )
        raise SystemExit(1)
if missing:
    print("active OpenCode config is missing reviewer lanes: " + ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)
def normalized_skill_body(text: str) -> str:
    parts = text.split("---", 2)
    body = parts[2] if len(parts) == 3 else text
    return " ".join(body.split())

def normalized_skill_frontmatter(text: str) -> tuple[tuple[str, str], ...]:
    parts = text.split("---", 2)
    if len(parts) != 3:
        return ()
    lines = parts[1].splitlines()
    fields: dict[str, list[str]] = {}
    current_key = ""
    for line in lines:
        if line and not line.startswith((" ", "\t")) and ":" in line:
            current_key, value = line.split(":", 1)
            current_key = current_key.strip()
            value = value.strip()
            if value in {">", "|-", ">-", "|"}:
                value = ""
            fields[current_key] = [value.strip("\"'")]
        elif current_key and (line.startswith(" ") or line.startswith("\t")):
            fields[current_key].append(line.strip())
    return tuple(
        sorted(
            (key, " ".join(" ".join(values).strip("\"'").split()))
            for key, values in fields.items()
        )
    )

if normalized_skill_frontmatter(skill_text) != normalized_skill_frontmatter(source_skill_text):
    print("active OpenCode reviewer skill frontmatter differs from Rulesync source", file=sys.stderr)
    raise SystemExit(1)
if normalized_skill_body(skill_text) != normalized_skill_body(source_skill_text):
    print("active OpenCode reviewer skill differs from Rulesync source", file=sys.stderr)
    raise SystemExit(1)
if "OpenCode ownership" not in skill_text or "orchestrator" not in skill_text:
    print("active OpenCode reviewer skill is stale or not coordinator-neutral", file=sys.stderr)
    raise SystemExit(1)
PY
then
  printf 'FAILED: active OpenCode reviewer configuration is stale; deploy and restart before running this smoke test\n' >&2
  exit 1
fi

COMPATIBILITY_OUTPUT=""
if ! COMPATIBILITY_OUTPUT="$("$REPO_ROOT/deploy.sh" --compatibility-check 2>&1)"; then
  printf '%s\n' "$COMPATIBILITY_OUTPUT" >&2
  printf 'FAILED: OpenCode/OMO/plugin/SDK compatibility is not verified; runtime smoke is blocked\n' >&2
  exit 1
fi
if [[ "$COMPATIBILITY_OUTPUT" != *"COMPATIBILITY_STATUS=matched"* ]]; then
  printf '%s\n' "$COMPATIBILITY_OUTPUT" >&2
  printf 'FAILED: compatibility preflight did not produce a matched status; runtime smoke is blocked\n' >&2
  exit 1
fi
export OPENCODE_COMPATIBILITY_STATUS=matched
printf 'Compatibility preflight: matched OpenCode/OMO/plugin/SDK evidence\n'

DB_PATH="${OPENCODE_DB_PATH:-}"
if [[ -z "$DB_PATH" ]]; then
  DB_PATH="$(opencode db path)"
fi
if [[ ! -f "$DB_PATH" ]]; then
  printf 'FAILED: OpenCode session database does not exist: %s\n' "$DB_PATH" >&2
  exit 1
fi

RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/opencode-reviewer-runtime.XXXXXX")"
cleanup() {
  local status=$?
  if ! rm -rf -- "$RUN_DIR" || [[ -e "$RUN_DIR" ]]; then
    printf 'FAILED: smoke-test temporary directory cleanup failed: %s\n' "$RUN_DIR" >&2
    status=1
  fi
  exit "$status"
}
trap cleanup EXIT
case "$RUN_DIR/" in
  "$REPO_ROOT/"*)
    printf 'FAILED: smoke-test temporary directory must be outside the repository: %s\n' "$RUN_DIR" >&2
    exit 1
    ;;
esac

STDOUT_LOG="$RUN_DIR/stdout.log"
STDERR_LOG="$RUN_DIR/stderr.log"
BEFORE_SNAPSHOT="$RUN_DIR/repository-before.json"
AFTER_SNAPSHOT="$RUN_DIR/repository-after.json"
START_MS="$(python3 -c 'import time; print(time.time_ns() // 1_000_000)')"

snapshot_repository() {
  local destination="$1"
  python3 - "$REPO_ROOT" "$destination" <<'PY'
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
destination = Path(sys.argv[2])
snapshot = {}
for path in sorted(root.rglob("*")):
    if ".git" in path.parts:
        continue
    relative = path.relative_to(root).as_posix()
    file_stat = path.lstat()
    if path.is_symlink():
        snapshot[relative] = ["symlink", os.readlink(path)]
    elif path.is_dir():
        snapshot[relative] = ["directory", stat.S_IMODE(file_stat.st_mode)]
    elif path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot[relative] = [
            "file",
            stat.S_IMODE(file_stat.st_mode),
            file_stat.st_size,
            digest,
        ]
    else:
        snapshot[relative] = [
            "special",
            stat.S_IFMT(file_stat.st_mode),
            stat.S_IMODE(file_stat.st_mode),
        ]

destination.write_text(
    json.dumps(snapshot, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
}

if ! snapshot_repository "$BEFORE_SNAPSHOT"; then
  printf 'FAILED: could not snapshot the repository working tree before the smoke test\n' >&2
  exit 1
fi

PROMPT=$'Run a synthetic OpenCode reviewer runtime smoke test against this repository.\n\n'
PROMPT+=$'The OpenCode orchestrator is the sole coordinator and must use its preloaded reviewer workflow directly. Dispatch exactly one background specialist lane: reviewer-code. Do not dispatch reviewer, reviewer-simplifier, or any other reviewer-* lane, and do not use a direct fallback lane.\n\n'
PROMPT+=$'This smoke test is strictly read-only. Do not run Git or GitHub commands. Do not use edit, write, patch, apply_patch, ast_grep_replace, or any mutation-capable shell command. Do not create, delete, rename, or modify repository files. Use only read-only inspection needed to dispatch and reconcile reviewer-code.\n\n'
PROMPT+=$'Compatibility preflight has matched OpenCode, OMO, plugin, and SDK evidence; do not treat this smoke run as valid if that status is unavailable or skewed. The current host may expose only partial/observed effective permission state. When it does, the final Review Health must be Degraded/inconclusive and Effective permission evidence must be partial/observed; never claim Healthy or read-only verified from that partial state. Call task_result using the returned reviewer-code child session ID, not an alias. The final response must be the normal structured review report and must include Review Health with coordinator identity, raw and resolved REVIEWER_MAX_PARALLEL, completed lanes, failed or invalid lanes, runtime smoke evidence status, effective permission evidence, and repository immutability status. The effective resolved concurrency must be 1/batch. If any requested invariant cannot be proven, report degraded/inconclusive rather than claiming Healthy.'

set +e
opencode run \
  --agent orchestrator \
  --format json \
  --print-logs \
  --dir "$REPO_ROOT" \
  --title 'OpenCode reviewer runtime smoke' \
  "$PROMPT" >"$STDOUT_LOG" 2>"$STDERR_LOG"
OPENCODE_STATUS=$?
set -e
END_MS="$(python3 -c 'import time; print(time.time_ns() // 1_000_000)')"

if ! snapshot_repository "$AFTER_SNAPSHOT"; then
  printf 'FAILED: could not snapshot the repository working tree after the smoke test\n' >&2
  exit 1
fi

python3 - "$DB_PATH" "$REPO_ROOT" "$START_MS" "$END_MS" "$OPENCODE_STATUS" "$STDOUT_LOG" "$STDERR_LOG" "$BEFORE_SNAPSHOT" "$AFTER_SNAPSHOT" <<'PY'
from __future__ import annotations

import json
import re
import shlex
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote


_, raw_db_path, raw_root, raw_start_ms, raw_end_ms, raw_process_status, stdout_path, stderr_path, before_snapshot_path, after_snapshot_path = sys.argv
db_path = Path(raw_db_path).expanduser().resolve()
root = Path(raw_root).resolve()
start_ms = int(raw_start_ms)
end_ms = int(raw_end_ms)
process_status = int(raw_process_status)
failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def read_log(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        fail(f"cannot read captured OpenCode log {path}: {error}")
        return ""


stdout = read_log(stdout_path)
stderr = read_log(stderr_path)
if process_status != 0:
    fail(f"fresh OpenCode process exited with status {process_status}")

effective_permission_status = "unavailable"
repository_immutability_verified = False


def read_snapshot(path: str) -> tuple[dict, bool]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        snapshot = json.loads(raw)
    except (OSError, UnicodeDecodeError, TypeError, json.JSONDecodeError) as error:
        fail(f"cannot read repository snapshot {path}: {error}")
        return {}, False
    if not isinstance(snapshot, dict):
        fail(f"repository snapshot {path} must be a JSON object")
        return {}, False
    return snapshot, True


before_snapshot, before_snapshot_ok = read_snapshot(before_snapshot_path)
after_snapshot, after_snapshot_ok = read_snapshot(after_snapshot_path)
if not (before_snapshot_ok and after_snapshot_ok):
    fail("authoritative repository immutability snapshots were not both readable")
elif before_snapshot != after_snapshot:
    fail("repository working tree snapshot changed during the smoke test")
else:
    repository_immutability_verified = True

if not db_path.is_file():
    fail(f"OpenCode session database does not exist: {db_path}")
    print("FAILED: " + "; ".join(failures), file=sys.stderr)
    raise SystemExit(1)

uri = f"file:{quote(str(db_path), safe='/')}?mode=ro"
try:
    connection = sqlite3.connect(uri, uri=True)
except sqlite3.Error as error:
    fail(f"cannot open OpenCode session database read-only: {error}")
    print("FAILED: " + "; ".join(failures), file=sys.stderr)
    raise SystemExit(1)

try:
    table_names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    required_tables = {"session", "part", "message"}
    missing_tables = sorted(required_tables - table_names)
    if missing_tables:
        fail(
            "OpenCode database schema cannot prove session ownership/tool use; "
            f"missing tables: {', '.join(missing_tables)}"
        )

    missing_session_columns: list[str] = []
    missing_part_columns: list[str] = []
    missing_message_columns: list[str] = []
    if not missing_tables:
        session_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(session)")
        }
        part_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(part)")
        }
        required_session_columns = {
            "id",
            "parent_id",
            "agent",
            "title",
            "directory",
            "permission",
            "time_created",
        }
        required_part_columns = {
            "id",
            "message_id",
            "session_id",
            "data",
            "time_created",
        }
        message_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(message)")
        }
        required_message_columns = {
            "id",
            "session_id",
            "data",
            "time_created",
        }
        missing_session_columns = sorted(required_session_columns - session_columns)
        missing_part_columns = sorted(required_part_columns - part_columns)
        missing_message_columns = sorted(required_message_columns - message_columns)
        if missing_session_columns or missing_part_columns or missing_message_columns:
            missing = []
            if missing_session_columns:
                missing.append("session." + ", ".join(missing_session_columns))
            if missing_part_columns:
                missing.append("part." + ", ".join(missing_part_columns))
            if missing_message_columns:
                missing.append("message." + ", ".join(missing_message_columns))
            fail(
                "OpenCode database schema cannot prove session ownership/tool use; "
                f"missing columns: {'; '.join(missing)}"
            )

    fresh_sessions = []
    schema_verified = not (
        missing_tables
        or missing_session_columns
        or missing_part_columns
        or missing_message_columns
    )
    if schema_verified:
        fresh_sessions = connection.execute(
            """
            SELECT id, parent_id, agent, title, directory, time_created, permission
            FROM session
            WHERE time_created >= ? AND time_created <= ?
            ORDER BY time_created, id
            """,
            (start_ms, end_ms),
        ).fetchall()

    allowed_session_agents = {"orchestrator", "reviewer-code"}
    session_ids_seen: set[str] = set()
    for session in fresh_sessions:
        session_id, parent_id, agent, title, directory, time_created, permission = session
        if not isinstance(session_id, str) or not session_id:
            fail("fresh OpenCode session has an invalid id")
        elif session_id in session_ids_seen:
            fail(f"fresh OpenCode session id is duplicated: {session_id}")
        else:
            session_ids_seen.add(session_id)
        if parent_id is not None and (
            not isinstance(parent_id, str) or not parent_id
        ):
            fail("fresh OpenCode session has an invalid parent_id")
        if agent not in allowed_session_agents:
            fail(f"fresh OpenCode session has an unauthorized agent: {agent!r}")
        if not isinstance(title, str) or not title:
            fail("fresh OpenCode session has an invalid title")
        if directory != str(root):
            fail(f"fresh OpenCode session has an unexpected directory: {directory!r}")
        if not isinstance(time_created, int):
            fail("fresh OpenCode session has an invalid time_created value")
        if permission is not None and not isinstance(permission, (str, bytes)):
            fail("fresh OpenCode session has invalid permission data")

    coordinators = [
        session
        for session in fresh_sessions
        if session[2] == "orchestrator" and session[1] is None
    ]
    nested_orchestrators = [
        session
        for session in fresh_sessions
        if session[2] == "orchestrator" and session[1] is not None
    ]
    if nested_orchestrators:
        fail(
            "fresh OpenCode orchestrator session is not a root session: "
            + ", ".join(session[0] for session in nested_orchestrators)
        )
    if len(coordinators) != 1:
        fail(
            "expected exactly one fresh orchestrator coordinator session, "
            f"found {len(coordinators)}"
        )
        coordinator = coordinators[-1] if coordinators else None
    else:
        coordinator = coordinators[0]

    expected_lane_session_id = None
    if coordinator is not None:
        coordinator_id = coordinator[0]
        children = [session for session in fresh_sessions if session[1] == coordinator_id]
        if len(children) != 1:
            fail(
                "expected exactly one fresh coordinator child session, "
                f"found {len(children)}"
            )
        reviewer_code_children = [
            session for session in children if session[2] == "reviewer-code"
        ]
        if len(reviewer_code_children) != 1:
            fail(
                "expected exactly one orchestrator-parented reviewer-code lane, "
                f"found {len(reviewer_code_children)}"
            )
        else:
            expected_lane_session_id = reviewer_code_children[0][0]
            print(f"Coordinator: {coordinator_id} (orchestrator)")
            print(f"Reviewer lane: {reviewer_code_children[0][0]} (reviewer-code)")
            permission_raw = reviewer_code_children[0][6]
            try:
                permission_records = json.loads(permission_raw)
            except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
                fail(f"cannot parse reviewer-code effective permissions: {error}")
                permission_records = None
            if not isinstance(permission_records, list):
                fail("reviewer-code effective permissions must be a JSON list")
            else:
                known_permission_names = {
                    "read",
                    "edit",
                    "glob",
                    "grep",
                    "list",
                    "bash",
                    "task",
                    "external_directory",
                    "lsp",
                    "skill",
                    "todowrite",
                    "question",
                    "webfetch",
                    "websearch",
                    "codesearch",
                    "doom_loop",
                    "write",
                    "apply_patch",
                    "ast_grep_replace",
                    "delete",
                    "move",
                    "rename",
                    "git",
                    "github",
                    "task_result",
                    "task_cancel",
                    "task_message",
                    "task_revive",
                    "task_status",
                }
                mutation_permission_names = {
                    "bash",
                    "edit",
                    "write",
                    "apply_patch",
                    "ast_grep_replace",
                    "delete",
                    "move",
                    "rename",
                    "git",
                    "github",
                    "task",
                    "task_result",
                    "task_cancel",
                    "task_message",
                    "task_revive",
                    "task_status",
                    "todowrite",
                }
                invalid_permission_records: list[str] = []
                observed_permission_denials = set()
                for record in permission_records:
                    if not isinstance(record, dict):
                        invalid_permission_records.append("record is not an object")
                        continue
                    if set(record) != {"permission", "pattern", "action"}:
                        invalid_permission_records.append(
                            "record has an unexpected key set: "
                            + ", ".join(sorted(record))
                        )
                        continue
                    permission_name = record["permission"]
                    pattern = record["pattern"]
                    action = record["action"]
                    if (
                        not isinstance(permission_name, str)
                        or permission_name not in known_permission_names
                        or not isinstance(pattern, str)
                        or not isinstance(action, str)
                        or action not in {"ask", "allow", "deny"}
                    ):
                        invalid_permission_records.append(
                            f"invalid permission record: {record!r}"
                        )
                        continue
                    if permission_name in mutation_permission_names:
                        if pattern != "*" or action != "deny":
                            invalid_permission_records.append(
                                "mutation-capable permission is not wildcard-denied: "
                                + repr(record)
                            )
                        observed_permission_denials.add(permission_name)
                for error in invalid_permission_records:
                    fail("invalid reviewer-code effective permission record: " + error)
                missing_permission_denials = sorted(
                    {"task", "todowrite"} - observed_permission_denials
                )
                if missing_permission_denials:
                    fail(
                        "reviewer-code effective permissions do not deny: "
                        + ", ".join(missing_permission_denials)
                    )
                elif not invalid_permission_records:
                    effective_permission_status = "partial/observed"

        nested_reviewers = [session for session in fresh_sessions if session[2] == "reviewer"]
        if nested_reviewers:
            fail(
                "nested reviewer coordinator session exists: "
                + ", ".join(session[0] for session in nested_reviewers)
            )

        fallback_lanes = [
            session
            for session in fresh_sessions
            if isinstance(session[2], str)
            and session[2].startswith("reviewer-")
            and session[2] != "reviewer-code"
        ]
        non_orchestrator_reviewer_code = [
            session
            for session in fresh_sessions
            if session[2] == "reviewer-code" and session[1] != coordinator_id
        ]
        if fallback_lanes:
            fail(
                "unexpected direct/fallback reviewer lane sessions: "
                + ", ".join(session[0] for session in fallback_lanes)
            )
        if non_orchestrator_reviewer_code:
            fail(
                "reviewer-code lane has a non-orchestrator parent: "
                + ", ".join(
                    f"{session[0]} parent={session[1]!r}"
                    for session in non_orchestrator_reviewer_code
                )
            )

    text_parts: list[str] = []
    coordinator_text_parts: list[str] = []
    tool_parts: list[tuple[str, str, dict]] = []
    part_records: list[tuple[str, str, str]] = []
    part_ids: set[str] = set()
    part_message_ids: set[str] = set()
    message_records: dict[str, str] = {}
    terminal_session_ids: set[str] = set()
    fresh_ids = [session[0] for session in fresh_sessions]
    fresh_session_ids = set(fresh_ids)
    if fresh_ids and schema_verified:
        placeholders = ", ".join("?" for _ in fresh_ids)
        for part_id, message_id, session_id, raw_data in connection.execute(
            "SELECT id, message_id, session_id, CAST(data AS BLOB) FROM part WHERE time_created >= ? AND time_created <= ? ORDER BY time_created",
            (start_ms, end_ms),
        ):
            if not all(
                isinstance(value, str) and value
                for value in (part_id, message_id, session_id)
            ):
                fail("OpenCode part row has invalid id, message_id, or session_id")
                continue
            if part_id in part_ids:
                fail(f"OpenCode part id is duplicated: {part_id}")
                continue
            part_ids.add(part_id)
            part_records.append((part_id, message_id, session_id))
            part_message_ids.add(message_id)
            try:
                part = json.loads(raw_data)
            except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
                fail(f"cannot parse OpenCode part JSON: {error}")
                continue
            if not isinstance(part, dict):
                fail("OpenCode part JSON must be an object")
                continue
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
                if coordinator is not None and session_id == coordinator[0]:
                    coordinator_text_parts.append(part["text"])
            if part.get("type") == "tool":
                tool_name = part.get("tool")
                if not isinstance(tool_name, str) or not tool_name.strip():
                    fail("tool record has a missing or non-string tool name")
                else:
                    tool_parts.append((session_id, tool_name, part))

        for message_id, message_session_id, raw_data in connection.execute(
            "SELECT id, session_id, CAST(data AS BLOB) FROM message WHERE time_created >= ? AND time_created <= ? ORDER BY time_created",
            (start_ms, end_ms),
        ):
            if not isinstance(message_id, str) or not message_id:
                fail("OpenCode message row has an invalid id")
                continue
            if not isinstance(message_session_id, str) or not message_session_id:
                fail("OpenCode message row has an invalid session_id")
                continue
            if message_session_id not in fresh_session_ids:
                fail(
                    "OpenCode message references a session outside the runtime window: "
                    + message_session_id
                )
                continue
            if message_id in message_records:
                fail(f"OpenCode message id is duplicated: {message_id}")
                continue
            message_records[message_id] = message_session_id
            try:
                message = json.loads(raw_data)
            except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
                fail(f"cannot parse OpenCode message JSON: {error}")
                continue
            if not isinstance(message, dict):
                fail("OpenCode message JSON must be an object")
                continue
            if message.get("role") == "assistant" and "finish" in message:
                if message.get("finish") != "stop":
                    fail(
                        "assistant message has a non-terminal finish value: "
                        + repr(message.get("finish"))
                    )
                else:
                    terminal_session_ids.add(message_session_id)
    for _, message_id, part_session_id in part_records:
        if part_session_id not in fresh_session_ids:
            fail(f"OpenCode part references unknown session: {part_session_id}")
        message_session_id = message_records.get(message_id)
        if message_session_id is None:
            fail(f"OpenCode part references unknown message: {message_id}")
        elif message_session_id != part_session_id:
            fail(
                "OpenCode part/message session relationship is inconsistent: "
                f"part={part_session_id!r}, message={message_session_id!r}"
            )
    orphan_message_ids = set(message_records) - part_message_ids
    if orphan_message_ids:
        fail(
            "OpenCode messages are not referenced by any part: "
            + ", ".join(sorted(orphan_message_ids))
        )
    missing_terminal_sessions = fresh_session_ids - terminal_session_ids
    if missing_terminal_sessions:
        fail(
            "fresh sessions missing an assistant finish=stop terminal message: "
            + ", ".join(sorted(missing_terminal_sessions))
        )
finally:
    connection.close()

coordinator_report = "\n".join(coordinator_text_parts)
health_match = re.search(
    r"^##\s+Review Health\s*$([\s\S]*?)(?=^##\s+|\Z)",
    coordinator_report,
    re.IGNORECASE | re.MULTILINE,
)
if health_match is None:
    fail("coordinator did not emit a structured Review Health section")
    health_report = ""
else:
    health_report = health_match.group(1)

required_health_labels = (
    "Status",
    "Coordinator",
    "Concurrency",
    "Completed",
    "Failed or invalid",
    "Runtime smoke evidence",
    "Effective permission evidence",
    "Repository immutability",
)
for label in required_health_labels:
    if not re.search(
        rf"(?m)^\s*-\s+\*\*{re.escape(label)}\*\*:",
        health_report,
    ):
        fail(f"structured Review Health is missing field: {label}")
status_match = re.search(
    r"(?m)^\s*-\s+\*\*Status\*\*:\s*(.+)$",
    health_report,
)
status_value = status_match.group(1).strip() if status_match else ""
if effective_permission_status == "partial/observed":
    if not re.search(r"Degraded/inconclusive", status_value, re.IGNORECASE):
        fail("structured Review Health must be Degraded/inconclusive for partial permissions")
    if re.search(r"\bHealthy\b", status_value):
        fail("structured Review Health must not claim Healthy for partial permissions")
else:
    if not re.search(r"\bHealthy\b", status_value):
        fail("structured Review Health does not report Healthy status")
if not re.search(
    r"(?m)^\s*-\s+\*\*Coordinator\*\*:.*\borchestrator\b",
    health_report,
    re.IGNORECASE,
):
    fail("structured Review Health does not identify orchestrator coordinator")
if not re.search(
    r"(?m)^\s*-\s+\*\*Concurrency\*\*:.*(?:→|->|=>).*\b1\s*/\s*batch",
    health_report,
):
    fail("structured Review Health does not report resolved concurrency 1/batch")
if not re.search(
    r"(?m)^\s*-\s+\*\*Runtime smoke evidence\*\*:.*(?:available and passed|passed)",
    health_report,
    re.IGNORECASE,
):
    fail("structured Review Health does not report passed runtime smoke evidence")
if not re.search(
    r"(?m)^\s*-\s+\*\*Effective permission evidence\*\*:.*(?:read-only verified|partial/observed|unavailable|mismatch)",
    health_report,
    re.IGNORECASE,
):
    fail("structured Review Health does not report verified effective permissions")
permission_evidence_match = re.search(
    r"(?m)^\s*-\s+\*\*Effective permission evidence\*\*:.*$",
    health_report,
)
permission_evidence_value = (
    permission_evidence_match.group(0).casefold()
    if permission_evidence_match
    else ""
)
if effective_permission_status == "partial/observed":
    if re.search(r"(?<!not )\bread-only verified\b", permission_evidence_value):
        fail("partial/observed permissions must not be reported as read-only verified")
    if not re.search(r"\bpartial/observed\b", permission_evidence_value):
        fail("partial/observed permissions must be reported as partial/observed")
if effective_permission_status == "unavailable":
    fail("effective permission evidence is unavailable; runtime health is inconclusive")
if not re.search(
    r"(?m)^\s*-\s+\*\*Repository immutability\*\*:.*(?:authoritative|unchanged|inspected)",
    health_report,
    re.IGNORECASE,
):
    fail("structured Review Health does not report authoritative repository immutability evidence")
if effective_permission_status == "read-only verified":
    print("Effective permission evidence: read-only verified from session.permission")
else:
    print(f"Effective permission evidence: {effective_permission_status}")
if repository_immutability_verified:
    print("Repository immutability: authoritative before/after working-tree snapshots unchanged")
else:
    print("Repository immutability: unavailable or mismatch")

if coordinator is not None:
    coordinator_id = coordinator[0]
    dispatch: dict = {}
    dispatch_metadata: dict = {}
    dispatches = [
        part
        for session_id, tool_name, part in tool_parts
        if session_id == coordinator_id and tool_name == "task"
    ]
    if len(dispatches) != 1:
        fail(
            "authoritative coordinator tool records must contain exactly one task dispatch, "
            f"found {len(dispatches)}"
        )
    else:
        dispatch = dispatches[0]
        state = dispatch.get("state")
        state = state if isinstance(state, dict) else {}
        dispatch_input = state.get("input")
        dispatch_input = dispatch_input if isinstance(dispatch_input, dict) else {}
        dispatch_metadata = state.get("metadata")
        dispatch_metadata = (
            dispatch_metadata if isinstance(dispatch_metadata, dict) else {}
        )
        dispatch_call_id = dispatch.get("callID")
        if not isinstance(dispatch_call_id, str) or not dispatch_call_id:
            fail("background task dispatch call ID must be a non-empty string")
        if dispatch_input.get("subagent_type") != "reviewer-code":
            fail("authoritative task metadata does not identify reviewer-code")
        if dispatch_metadata.get("background") is not True:
            fail("authoritative task metadata does not prove background=true")
        job_id = dispatch_metadata.get("jobId")
        child_id = dispatch_metadata.get("sessionId")
        parent_id = dispatch_metadata.get("parentSessionId")
        for key, value in (("jobId", job_id), ("sessionId", child_id), ("parentSessionId", parent_id)):
            if value is not None and (not isinstance(value, str) or not value):
                fail(f"authoritative task metadata has invalid optional {key}")
        if child_id is not None and child_id != expected_lane_session_id:
            fail("authoritative task session metadata does not identify the reviewer-code child")
        if parent_id is not None and parent_id != coordinator_id:
            fail("authoritative task metadata does not identify the orchestrator parent")
        if state.get("status") != "completed":
            fail(
                "authoritative background task dispatch was not reconciled to completed status: "
                f"{state.get('status')!r}"
            )

    reconciliations = [
        part
        for session_id, tool_name, part in tool_parts
        if session_id == coordinator_id and tool_name == "task_result"
    ]
    if len(reconciliations) != 1:
        fail(
            "authoritative coordinator tool records must contain exactly one task_result reconciliation, "
            f"found {len(reconciliations)}"
        )
    else:
        reconciliation = reconciliations[0]
        reconciliation_state = (
            reconciliation.get("state")
            if isinstance(reconciliation.get("state"), dict)
            else {}
        )
        if reconciliation_state.get("status") != "completed":
            fail("authoritative task_result metadata does not prove completed reconciliation")
        reconciliation_metadata = (
            reconciliation_state.get("metadata")
            if isinstance(reconciliation_state.get("metadata"), dict)
            else {}
        )
        reconciliation_input = reconciliation_state.get("input")
        reconciliation_input = (
            reconciliation_input
            if isinstance(reconciliation_input, dict)
            else {}
        )
        if reconciliation_input.get("task_id") != expected_lane_session_id:
            fail(
                "task_result input does not identify the reviewer-code child session: "
                f"expected {expected_lane_session_id!r}, got "
                f"{reconciliation_input.get('task_id')!r}"
            )
    if expected_lane_session_id not in terminal_session_ids:
        fail("reviewer-code session has no authoritative terminal assistant message")

    expected_session_ids = {coordinator_id}
    if expected_lane_session_id is not None:
        expected_session_ids.add(expected_lane_session_id)
    unexpected_sessions = [
        session
        for session in fresh_sessions
        if session[0] not in expected_session_ids
    ]
    if unexpected_sessions:
        fail(
            "unexpected coordinator descendant or sibling sessions: "
            + ", ".join(
                f"{session[0]} agent={session[2]!r} parent={session[1]!r}"
                for session in unexpected_sessions
            )
        )

allowed_read_only_tools = {
    "ast_grep_search",
    "bash",
    "codesearch",
    "command",
    "exec",
    "glob",
    "grep",
    "list",
    "lsp",
    "read",
    "shell",
    "task",
    "task_result",
    "terminal",
}
for _, tool_name, _ in tool_parts:
    if tool_name not in allowed_read_only_tools:
        fail(
            "unrecognized tool is not allowed by the smoke-test read-only policy: "
            + tool_name
        )

for session_id, tool_name, _ in tool_parts:
    if tool_name in {"task", "task_result"} and coordinator is not None:
        if session_id != coordinator[0]:
            fail(
                "nested task-control record is not allowed outside the coordinator: "
                f"session={session_id} tool={tool_name}"
            )

for _, tool_name, part in tool_parts:
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    tool_input = state.get("input") if isinstance(state.get("input"), dict) else {}
    if not tool_input and isinstance(part.get("input"), dict):
        tool_input = part["input"]
    command = tool_input.get("command", "")
    if tool_name in {
        "edit",
        "write",
        "patch",
        "apply_patch",
        "ast_grep_replace",
        "delete",
        "move",
        "rename",
        "git",
        "github",
    }:
        fail(f"forbidden mutation-capable tool requested: {tool_name}")
    if tool_name in {"bash", "shell", "command", "exec", "terminal"}:
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        if state.get("status") != "completed":
            fail(f"shell tool record is not a completed, classifiable execution: {tool_name}")
        if not isinstance(command, str) or not command.strip():
            fail("shell tool execution cannot be classified as read-only")
            continue
        try:
            argv = tuple(shlex.split(command, posix=True))
        except ValueError as error:
            fail(f"shell command cannot be parsed under the read-only policy: {error}")
            continue
        safe_commands = {("pwd",), ("date", "+%s")}
        if argv not in safe_commands:
            fail(
                "shell execution is outside the strict read-only allowlist "
                f"(interpreters, nested shells, and file writes are rejected): {command}"
            )

if failures:
    print("FAILED: " + "; ".join(failures), file=sys.stderr)
    raise SystemExit(1)

if effective_permission_status == "partial/observed":
    print("Runtime smoke evidence: DEGRADED (complete permission state unavailable)")
else:
    print("Runtime smoke evidence: PASS")
print("Compatibility evidence: matched OpenCode/OMO/plugin/SDK preflight")
print("Resolved concurrency: REVIEWER_MAX_PARALLEL=1 -> 1/batch")
print("Recorded reconciliation: background task metadata, completed task_result, and terminal child session verified")
print("Forbidden mutation-capable tool execution: none observed")
if repository_immutability_verified:
    print("Repository immutability: authoritative before/after working-tree snapshots unchanged")
else:
    print("Repository immutability: unavailable or mismatch")
PY
