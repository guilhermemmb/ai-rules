#!/usr/bin/env bash

set -eo pipefail

if [[ -z "${AI_RULES_ZSH_BOOTSTRAPPED:-}" ]]; then
  exec zsh -lc 'source "$HOME/.zshrc"; export AI_RULES_ZSH_BOOTSTRAPPED=1; exec bash "$1" "$2"' -- "$0" "${1:-}"
fi
set -u

usage() {
  printf '%s\n' \
    'Usage: smoke-opencode-fixer-runtime.sh --run' \
    '' \
    'This opt-in command starts a fresh OpenCode multi-fixer runtime smoke test in an isolated temporary repository.'
}

if [[ "${1:-}" != "--run" || $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"

if ! command -v opencode >/dev/null 2>&1; then
  printf 'FAILED: opencode is not available on PATH\n' >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf 'FAILED: python3 is required for isolated runtime inspection\n' >&2
  exit 1
fi

ACTIVE_CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
ACTIVE_OMO_PATH="$ACTIVE_CONFIG_DIR/oh-my-opencode-slim.json"
SOURCE_OMO_PATH="$REPO_ROOT/oh-my-opencode-slim.json"
if ! python3 - "$ACTIVE_OMO_PATH" "$SOURCE_OMO_PATH" <<'PY'
import json
import sys
from pathlib import Path

active_path = Path(sys.argv[1])
source_path = Path(sys.argv[2])
try:
    active = json.loads(active_path.read_text(encoding="utf-8"))
    source = json.loads(source_path.read_text(encoding="utf-8"))
except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
    print(f"active OpenCode fixer configuration is unavailable: {error}", file=sys.stderr)
    raise SystemExit(1)

active_preset = active.get("preset", "bifrost")
source_preset = source.get("preset", "bifrost")
active_fixer = active.get("presets", {}).get(active_preset, {}).get("fixer", {})
source_fixer = source.get("presets", {}).get(source_preset, {}).get("fixer", {})
if active_preset != source_preset or active_fixer != source_fixer:
    print("active OpenCode fixer configuration differs from Rulesync source", file=sys.stderr)
    raise SystemExit(1)
if "fixer" not in active_fixer.get("skills", []):
    print("active OpenCode fixer does not load the fixer skill", file=sys.stderr)
    raise SystemExit(1)
PY
then
  printf 'FAILED: active OpenCode fixer configuration is stale; deploy and restart before running this smoke test\n' >&2
  exit 1
fi

RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/opencode-fixer-runtime.XXXXXX")"
cleanup() {
  local status=$?
  if ! rm -rf -- "$RUN_DIR" || [[ -e "$RUN_DIR" ]]; then
    printf 'FAILED: smoke-test temporary directory cleanup failed: %s\n' "$RUN_DIR" >&2
    status=1
  fi
  exit "$status"
}
trap cleanup EXIT

RUN_REPO="$RUN_DIR/isolated-repo"
mkdir -- "$RUN_REPO"
python3 - "$RUN_REPO" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
for name in ("task-one.txt", "task-two.txt", "task-three.txt"):
    (root / name).write_text(f"fixture for {name}\n", encoding="utf-8")
PY

BEFORE_SNAPSHOT="$RUN_DIR/repository-before.json"
AFTER_SNAPSHOT="$RUN_DIR/repository-after.json"
STDOUT_LOG="$RUN_DIR/stdout.log"
STDERR_LOG="$RUN_DIR/stderr.log"
DB_PATH="${OPENCODE_DB_PATH:-}"
if [[ -z "$DB_PATH" ]]; then
  DB_PATH="$(opencode db path)"
fi
if [[ ! -f "$DB_PATH" ]]; then
  printf 'FAILED: OpenCode session database does not exist: %s\n' "$DB_PATH" >&2
  exit 1
fi

snapshot_repository() {
  local destination="$1"
  python3 - "$RUN_REPO" "$destination" <<'PY'
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
    relative = path.relative_to(root).as_posix()
    file_stat = path.lstat()
    if path.is_symlink():
        snapshot[relative] = ["symlink", os.readlink(path)]
    elif path.is_dir():
        snapshot[relative] = ["directory", stat.S_IMODE(file_stat.st_mode)]
    elif path.is_file():
        snapshot[relative] = ["file", stat.S_IMODE(file_stat.st_mode), file_stat.st_size, hashlib.sha256(path.read_bytes()).hexdigest()]
    else:
        snapshot[relative] = ["special", stat.S_IFMT(file_stat.st_mode), stat.S_IMODE(file_stat.st_mode)]
destination.write_text(json.dumps(snapshot, sort_keys=True) + "\n", encoding="utf-8")
PY
}

START_MS="$(python3 -c 'import time; print(time.time_ns() // 1_000_000)')"
snapshot_repository "$BEFORE_SNAPSHOT"

PROMPT=$'Run a synthetic OpenCode multi-fixer scheduler smoke test in this isolated repository.\n\n'
PROMPT+=$'The orchestrator must dispatch exactly three fresh @fixer children in one batch, all with background=true and direct parentage to this orchestrator. Never dispatch a fourth fixer or any unrelated implementation child.\n\n'
PROMPT+=$'Use these exact independent tasks and hard write sets:\n- task-one: Files: task-one.txt; write_set: task-one.txt\n- task-two: Files: task-two.txt; write_set: task-two.txt\n- task-three: Files: task-three.txt; write_set: task-three.txt\nDo not create or modify any other file, including reports, planning artifacts, generated outputs, lockfiles, or temporary files.\n\n'
PROMPT+=$'Dispatch all three tasks with the task tool in the same batch. Record the exact returned child session IDs and job IDs; wait for every child; call task_result once per exact child session ID, never an alias. Reconcile all three results before continuing. Each fixer must actually change its assigned file and include this exact line in its own child report: FIXER_REPORT path=<assigned-path> status=DONE. A report without the corresponding snapshot change is a failure.\n\n'
PROMPT+=$'Review each DONE fixer child individually through the preloaded OpenCode reviewer workflow before declaring it releasable. For this smoke, dispatch exactly one reviewer-code task per fixer, with review_target_session=<fixer-session-id> in its task input. Each reviewer task must be backgrounded, parented to the orchestrator, reconciled by its exact reviewer session ID, and return this exact line in the reviewer session report: REVIEW_RESULT target=<fixer-session-id> status=passed. Do not use parent self-reported review text as evidence. If any result is missing, malformed, failed, timed out, NEEDS_CONTEXT, BLOCKED, unowned, misattributed, or extra, fail closed and report it.\n'

set +e
opencode run \
  --agent orchestrator \
  --format json \
  --print-logs \
  --dir "$RUN_REPO" \
  --title 'OpenCode fixer runtime smoke' \
  "$PROMPT" >"$STDOUT_LOG" 2>"$STDERR_LOG"
OPENCODE_STATUS=$?
set -e
END_MS="$(python3 -c 'import time; print(time.time_ns() // 1_000_000)')"
snapshot_repository "$AFTER_SNAPSHOT"

python3 - "$DB_PATH" "$RUN_REPO" "$START_MS" "$END_MS" "$OPENCODE_STATUS" "$BEFORE_SNAPSHOT" "$AFTER_SNAPSHOT" <<'PY'
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

_, raw_db, raw_root, raw_start, raw_end, raw_status, before_path, after_path = sys.argv
db_path = Path(raw_db).expanduser().resolve()
root = Path(raw_root).resolve()
start_ms = int(raw_start)
end_ms = int(raw_end)
failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def read_json(path: str) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"cannot read JSON evidence {path}: {error}")
        return {}


if int(raw_status) != 0:
    fail(f"fresh OpenCode process exited with status {raw_status}")

before = read_json(before_path)
after = read_json(after_path)
changed_paths: set[str] = set()
if not isinstance(before, dict) or not isinstance(after, dict):
    fail("isolated repository snapshots must be JSON objects")
else:
    changed_paths = {
        *before,
        *after,
    } - {
        path for path in before.keys() & after.keys() if before[path] == after[path]
    }
    expected_paths = {"task-one.txt", "task-two.txt", "task-three.txt"}
    unowned = sorted(set(changed_paths) - expected_paths)
    if unowned:
        fail("unowned repository changes detected: " + ", ".join(unowned))
    missing_changes = sorted(expected_paths - changed_paths)
    if missing_changes:
        fail("expected fixer write-set paths were not changed: " + ", ".join(missing_changes))
    if changed_paths != expected_paths:
        fail("isolated fixer run did not produce exactly one change for each expected write-set path")
    if any(path.endswith((".lock", ".lockfile")) or "report" in path or "planning" in path for path in changed_paths):
        fail("generated, lockfile, report, or planning artifact changed in isolated repository")

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
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    required_tables = {"session", "part", "message"}
    if missing := sorted(required_tables - tables):
        fail("OpenCode database schema cannot prove fixer ownership; missing tables: " + ", ".join(missing))
        raise SystemExit(1)
    session_columns = {row[1] for row in connection.execute("PRAGMA table_info(session)")}
    part_columns = {row[1] for row in connection.execute("PRAGMA table_info(part)")}
    message_columns = {row[1] for row in connection.execute("PRAGMA table_info(message)")}
    required_columns = {
        "session": {"id", "parent_id", "agent", "directory", "time_created"},
        "part": {"id", "session_id", "data", "time_created"},
        "message": {"id", "session_id", "data", "time_created"},
    }
    for table, actual, required in (("session", session_columns, required_columns["session"]), ("part", part_columns, required_columns["part"]), ("message", message_columns, required_columns["message"])):
        if missing := sorted(required - actual):
            fail(f"OpenCode database schema cannot prove fixer ownership; missing {table} columns: {', '.join(missing)}")

    sessions = connection.execute(
        "SELECT id, parent_id, agent, directory, time_created FROM session WHERE time_created >= ? AND time_created <= ? ORDER BY time_created, id",
        (start_ms, end_ms),
    ).fetchall()
    coordinators = [row for row in sessions if row[2] == "orchestrator" and row[1] is None]
    if len(coordinators) != 1:
        fail(f"expected exactly one fresh root orchestrator session, found {len(coordinators)}")
        coordinator = coordinators[0] if coordinators else None
    else:
        coordinator = coordinators[0]
    if coordinator is None:
        raise SystemExit(1)
    coordinator_id = coordinator[0]
    if coordinator[3] != str(root):
        fail(f"orchestrator used unexpected directory: {coordinator[3]!r}")
    nested_orchestrators = [row[0] for row in sessions if row[2] == "orchestrator" and row[1] is not None]
    if nested_orchestrators:
        fail("nested orchestrator sessions exist: " + ", ".join(nested_orchestrators))
    children = [row for row in sessions if row[1] == coordinator_id]
    fixer_children = [row for row in children if row[2] == "fixer"]
    if len(fixer_children) != 3:
        fail(f"expected exactly three orchestrator-parented fixer children, found {len(fixer_children)}")
    allowed_child_agents = {
        "fixer",
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
    unexpected_children = [row for row in children if row[2] not in allowed_child_agents]
    if unexpected_children:
        fail("unexpected orchestrator child sessions: " + ", ".join(row[0] for row in unexpected_children))

    child_ids = {row[0] for row in fixer_children}
    expected_names = {"task-one.txt", "task-two.txt", "task-three.txt"}
    parts = []
    child_report_text: dict[str, list[str]] = {}
    child_mutation_paths: dict[str, set[str]] = {}
    for row in connection.execute(
        "SELECT session_id, data FROM part WHERE time_created >= ? AND time_created <= ? ORDER BY time_created",
        (start_ms, end_ms),
    ):
        try:
            part = json.loads(row[1])
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            fail(f"cannot parse OpenCode part JSON: {error}")
            continue
        if isinstance(part, dict):
            parts.append((row[0], part))
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                child_report_text.setdefault(row[0], []).append(part["text"])
            if row[0] in child_ids and part.get("type") == "tool":
                tool_name = part.get("tool")
                if tool_name in {"edit", "write", "apply_patch", "ast_grep_replace", "delete", "move", "rename"}:
                    state = part.get("state") if isinstance(part.get("state"), dict) else {}
                    tool_input = state.get("input") if isinstance(state.get("input"), dict) else part.get("input", {})
                    for key in ("filePath", "file_path", "path", "oldPath", "newPath", "target", "destination"):
                        candidate = tool_input.get(key)
                        if not isinstance(candidate, str) or not candidate:
                            continue
                        candidate_path = Path(candidate).expanduser()
                        try:
                            normalized_path = candidate_path.resolve().relative_to(root).as_posix()
                        except ValueError:
                            normalized_path = candidate_path.as_posix().removeprefix("./")
                        child_mutation_paths.setdefault(row[0], set()).add(normalized_path)

    task_records = []
    reconciliations = []
    for session_id, part in parts:
        if session_id != coordinator_id:
            continue
        if part.get("type") != "tool":
            continue
        tool_name = part.get("tool")
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        tool_input = state.get("input") if isinstance(state.get("input"), dict) else part.get("input", {})
        metadata = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
        if tool_name == "task":
            task_records.append((tool_input, metadata, state))
        elif tool_name == "task_result":
            reconciliations.append((tool_input, state))

    reviewer_agents = {
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
    fixer_dispatches = [
        record for record in task_records if record[0].get("subagent_type") == "fixer"
    ]
    reviewer_dispatches = [
        record for record in task_records if record[0].get("subagent_type") in reviewer_agents
    ]
    unsupported_task_records = [
        record for record in task_records
        if record[0].get("subagent_type") not in reviewer_agents | {"fixer"}
    ]
    if unsupported_task_records:
        fail("coordinator issued task records for unsupported child agents")
    if len(fixer_dispatches) != 3:
        fail(f"expected exactly three fixer task dispatches, found {len(fixer_dispatches)}")
    if len(reviewer_dispatches) != 3:
        fail(f"expected exactly three reviewer task dispatches, found {len(reviewer_dispatches)}")
    returned_ids: set[str] = set()
    write_sets: list[str] = []
    dispatch_write_sets: dict[str, str] = {}
    for tool_input, metadata, state in fixer_dispatches:
        if tool_input.get("subagent_type") != "fixer":
            fail("task dispatch does not target fixer")
        if metadata.get("background") is not True:
            fail("fixer task dispatch does not prove background=true")
        job_id = metadata.get("jobId")
        if not isinstance(job_id, str) or not job_id:
            fail("fixer task metadata does not prove a returned job ID")
        if metadata.get("parentSessionId") not in {None, coordinator_id}:
            fail("fixer task metadata has the wrong parent session ID")
        child_id = metadata.get("sessionId")
        if not isinstance(child_id, str) or child_id not in child_ids:
            fail("fixer task metadata does not identify an exact returned child session ID")
        else:
            returned_ids.add(child_id)
        if state.get("status") != "completed":
            fail("fixer task dispatch was not reconciled to completed status")
        declared_write_set = metadata.get("write_set")
        description = " ".join(str(tool_input.get(key, "")) for key in ("description", "prompt", "task"))
        if declared_write_set is not None:
            description += f" write_set: {declared_write_set}"
        match = re.search(r"write_set\s*:\s*([^;\n]+)", description, re.IGNORECASE)
        if match is None:
            fail("fixer task dispatch is missing a declared write_set")
        else:
            write_sets.append(match.group(1).strip())
            write_set = match.group(1).strip()
            if isinstance(child_id, str) and child_id:
                if child_id in dispatch_write_sets:
                    fail(f"multiple fixer dispatches claim child session {child_id}")
                dispatch_write_sets[child_id] = write_set
                if write_set not in expected_names:
                    fail(f"fixer child {child_id} declares an unexpected write-set path: {write_set}")
    if set(write_sets) != expected_names or len(write_sets) != len(set(write_sets)):
        fail("fixer dispatches do not prove three distinct declared write sets")
    if len(returned_ids) != 3 or set(dispatch_write_sets) != returned_ids:
        fail("fixer dispatches do not bind three unique write sets to three returned child sessions")
    children_by_id = {row[0]: row for row in children}
    reviewer_session_ids: set[str] = set()
    reviewer_targets: dict[str, str] = {}
    for tool_input, metadata, state in reviewer_dispatches:
        if tool_input.get("subagent_type") != "reviewer-code":
            fail("reviewer task records must target reviewer-code for this smoke")
        if metadata.get("background") is not True:
            fail("reviewer task dispatch does not prove background=true")
        if not isinstance(metadata.get("jobId"), str) or not metadata["jobId"]:
            fail("reviewer task metadata does not prove a returned job ID")
        if metadata.get("parentSessionId") not in {None, coordinator_id}:
            fail("reviewer task metadata has the wrong parent session ID")
        reviewer_id = metadata.get("sessionId")
        reviewer_session = children_by_id.get(reviewer_id)
        if not isinstance(reviewer_id, str) or reviewer_session is None:
            fail("reviewer task metadata does not identify an orchestrator child session")
            continue
        if reviewer_session[2] != "reviewer-code" or reviewer_session[1] != coordinator_id:
            fail(f"reviewer session {reviewer_id} has the wrong reviewer identity or parent")
        reviewer_session_ids.add(reviewer_id)
        review_input = " ".join(
            str(tool_input.get(key, "")) for key in ("description", "prompt", "task")
        )
        target_match = re.search(
            r"review_target_session\s*=\s*([^;\n\s]+)", review_input, re.IGNORECASE
        )
        if target_match is None or target_match.group(1) not in returned_ids:
            fail(f"reviewer session {reviewer_id} is missing a valid fixer target session")
        else:
            target_id = target_match.group(1)
            if target_id in reviewer_targets:
                fail(f"multiple reviewer tasks claim fixer session {target_id}")
            reviewer_targets[target_id] = reviewer_id
        if state.get("status") != "completed":
            fail(f"reviewer task for session {reviewer_id} was not completed")
    if len(reviewer_session_ids) != 3 or set(reviewer_targets) != returned_ids:
        fail("reviewer task records do not bind one reviewer session to each fixer child")
    expected_child_session_ids = returned_ids | reviewer_session_ids
    actual_child_session_ids = {row[0] for row in children}
    if len(expected_child_session_ids) != 6 or actual_child_session_ids != expected_child_session_ids:
        extra_child_ids = sorted(actual_child_session_ids - expected_child_session_ids)
        missing_child_ids = sorted(expected_child_session_ids - actual_child_session_ids)
        fail(
            "orchestrator-parented child sessions must equal exactly the three fixer "
            "and three reviewer sessions; "
            f"extra={extra_child_ids}, missing={missing_child_ids}"
        )

    fixer_reconciled_ids = []
    reviewer_reconciled_ids = []
    for tool_input, state in reconciliations:
        if state.get("status") != "completed":
            fail("task_result reconciliation is not completed")
        task_id = tool_input.get("task_id")
        if task_id in returned_ids:
            fixer_reconciled_ids.append(task_id)
        elif task_id in reviewer_session_ids:
            reviewer_reconciled_ids.append(task_id)
        else:
            fail("task_result does not use an exact returned fixer or reviewer session ID")
    if len(fixer_reconciled_ids) != 3 or set(fixer_reconciled_ids) != returned_ids:
        fail("expected one completed task_result reconciliation for each fixer child")
    if len(reviewer_reconciled_ids) != 3 or set(reviewer_reconciled_ids) != reviewer_session_ids:
        fail("expected one completed task_result reconciliation for each reviewer session")
    for child_id, write_set in dispatch_write_sets.items():
        if write_set not in changed_paths:
            fail(f"fixer child {child_id} did not change its assigned write-set path {write_set}")
        report = "\n".join(child_report_text.get(child_id, []))
        if not re.search(
            rf"FIXER_REPORT\s+path={re.escape(write_set)}\s+status=DONE",
            report,
        ):
            fail(
                f"fixer child {child_id} did not report its assigned changed path "
                f"with status DONE: {write_set}"
            )
        mutation_paths = child_mutation_paths.get(child_id, set())
        if mutation_paths != {write_set}:
            fail(
                f"fixer child {child_id} mutation evidence is missing or misattributed: "
                f"expected {write_set}, observed {sorted(mutation_paths)}"
            )
finally:
    connection.close()

for fixer_id, reviewer_id in reviewer_targets.items():
    reviewer_report = "\n".join(child_report_text.get(reviewer_id, []))
    if not re.search(
        rf"REVIEW_RESULT\s+target={re.escape(fixer_id)}\s+status=passed",
        reviewer_report,
    ):
        fail(
            f"reviewer session {reviewer_id} has no passing review result "
            f"for fixer session {fixer_id}"
        )

if failures:
    print("FAILED: " + "; ".join(failures), file=sys.stderr)
    raise SystemExit(1)

print("Runtime smoke evidence: PASS")
print("Fixer scheduler: exactly 3 background=true orchestrator-parented children")
print("Write-set evidence: three distinct hard allowlists; no unowned changes")
print("Reconciliation: exact child session IDs used for all task_result calls")
print("Review gates: one passing review recorded for every DONE fixer child")
PY
