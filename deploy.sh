#!/usr/bin/env bash
# ~/developer/dotfiles/ai-rules/deploy.sh
#
# Stage and force-replace the tracked OpenCode configuration only after
# validation succeeds. Worktrunk and wt-orca are
# installed from the sibling dotfiles directory; Orca runtime state is not a
# deployment input or output.
#
# Usage:
#   ./deploy.sh          — force-replace the live configuration
#   ./deploy.sh --force  — same as ./deploy.sh
#   ./deploy.sh --help   — show usage
set -euo pipefail
MV_BIN="${MV_BIN:-mv}"

SRCDIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DOTFILES_DIR="$(cd -P "$SRCDIR/.." && pwd -P)"

OPENDIR="${OPENCODE_CONFIG_DIR:-${HOME}/.config/opencode}"
OPENCODE_TRANSACTION_MARKER="${OPENDIR}.transaction"
OPENCODE_MANIFEST_NAME=".ai-rules.manifest.json"
OPENCODE_MANIFEST_PATH="$OPENDIR/$OPENCODE_MANIFEST_NAME"
WORKTRUNK_CONFIG_SOURCE="${WORKTRUNK_CONFIG_SOURCE:-$DOTFILES_DIR/worktrunk/config.toml}"
WORKTRUNK_INSTALLER="${WORKTRUNK_INSTALLER:-$DOTFILES_DIR/worktrunk-install.sh}"
WORKTRUNK_CONFIG_DESTINATION="${WORKTRUNK_CONFIG_DESTINATION:-${HOME}/.config/worktrunk/config.toml}"
WT_ORCA_SOURCE="${WT_ORCA_SOURCE:-$DOTFILES_DIR/wt-orca.sh}"
WT_ORCA_DESTINATION="${WT_ORCA_DESTINATION:-${HOME}/.local/bin/wt-orca}"
WORKTREE_STATE_SOURCE="${WORKTREE_STATE_SOURCE:-$DOTFILES_DIR/worktree-state.sh}"
WORKTREE_STATE_DESTINATION="${WORKTREE_STATE_DESTINATION:-$(dirname "$WT_ORCA_DESTINATION")/worktree-state.sh}"
DEPLOYMENT_LOCK_HELPER="${DEPLOYMENT_LOCK_HELPER:-$DOTFILES_DIR/deployment-lock.sh}"

RTK_BIN="${RTK_BIN:-}"
RTK_HOMEBREW_FORMULA="rtk-ai/tap/rtk"
RTK_PLUGIN_PATH="${OPENDIR}/plugins/rtk.ts"
REVIEW_PIPELINE_SKILL="review-pipeline"
REVIEW_PIPELINE_SKILL_PATH="skills/${REVIEW_PIPELINE_SKILL}/SKILL.md"
REVIEW_PIPELINE_REGISTRY_PATH="skills/${REVIEW_PIPELINE_SKILL}/pipeline.json"

# Rulesync is a repository-recorded convergence input. OMO always resolves the
# latest published release.
RULESYNC_VERSION="16.2.0"
OH_MY_OPENCODE_SLIM_PACKAGE="oh-my-opencode-slim"
RULESYNC_PACKAGE="rulesync@${RULESYNC_VERSION}"
OPENCODE_PACKAGE_CACHE_DIR="${OPENCODE_PACKAGE_CACHE_DIR:-${HOME}/.cache/opencode/packages}"
OH_MY_OPENCODE_SLIM_PACKAGE_JSON="${OH_MY_OPENCODE_SLIM_PACKAGE_JSON:-$OPENCODE_PACKAGE_CACHE_DIR/oh-my-opencode-slim/node_modules/oh-my-opencode-slim/package.json}"
OH_MY_OPENCODE_SLIM_NODE_MODULES_DIR="$(dirname "$OH_MY_OPENCODE_SLIM_PACKAGE_JSON")/.."
OPENCODE_SDK_PACKAGE_JSON="${OPENCODE_SDK_PACKAGE_JSON:-$OH_MY_OPENCODE_SLIM_NODE_MODULES_DIR/@opencode-ai/sdk/package.json}"
OPENCODE_PLUGIN_PACKAGE_JSON="${OPENCODE_PLUGIN_PACKAGE_JSON:-$OH_MY_OPENCODE_SLIM_NODE_MODULES_DIR/@opencode-ai/plugin/package.json}"
STAGE_ROOT=""
DEPLOY_SUCCEEDED=false
RECOVERY_ARTIFACTS_PRESERVED=false
OPENCODE_DISPLACED_PATH=""
OPENCODE_DISPLACED_IDENTITY=""

# ── parse args ──
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      shift
      ;;
    --help|-h)
      cat <<'EOF'
Usage: ./deploy.sh [--force]

  --force  Force-replace the live OpenCode configuration with the validated
           staged payload. This is equivalent to running ./deploy.sh.
  --help   Show this usage text.

Unknown flags, including --check and --compatibility-check, are rejected before
deployment. The deployment resolves the latest oh-my-opencode-slim release,
uses a transient recoverable transaction marker, and does not retain a backup
after successful completion.
EOF
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

red()   { printf '\033[31m%s\033[0m\n' "$1"; }
green() { printf '\033[32m%s\033[0m\n' "$1"; }
cyan()  { printf '\033[36m%s\033[0m\n' "$1"; }
yellow() { printf '\033[33m%s\033[0m\n' "$1"; }

force_recovery_warning() {
  yellow "  ⚠️  force deployment failed after OpenCode replacement; no cross-component rollback is available."
  yellow "     Recoverable transaction artifacts remain near $OPENDIR; inspect the marker and displaced path before retrying."
}

fail() {
  red "  ❌ $1" >&2
  return 1
}

[[ -f "$DEPLOYMENT_LOCK_HELPER" ]] || fail "shared deployment lock helper is missing: $DEPLOYMENT_LOCK_HELPER"
# shellcheck source=/dev/null
source "$DEPLOYMENT_LOCK_HELPER"

cleanup_stage() {
  local exit_code=$?
  if [[ $exit_code -ne 0 && ( -e "$OPENCODE_TRANSACTION_MARKER" || -L "$OPENCODE_TRANSACTION_MARKER" ) ]]; then
    force_recovery_warning
  fi
  if [[ -n "$STAGE_ROOT" && -d "$STAGE_ROOT" ]]; then
    if [[ "$RECOVERY_ARTIFACTS_PRESERVED" = true ]]; then
      yellow "  ⚠️  preserving private staging/recovery artifacts at $STAGE_ROOT"
    elif rm -rf "$STAGE_ROOT"; then
      STAGE_ROOT=""
    else
      red "  ❌ could not remove private staging artifacts: $STAGE_ROOT"
      exit_code=1
    fi
  fi
  if [[ "${DEPLOYMENT_LOCK_HELD:-false}" = true && "${DEPLOYMENT_LOCK_REENTRANT:-false}" != true ]] &&
    ! deployment_lock_release; then
    exit_code=1
  fi
  exit "$exit_code"
}
trap cleanup_stage EXIT

resolve_command() {
  local variable_name="$1"
  local label="$2"
  local fallback="$3"
  local configured="${!variable_name:-}"
  local resolved=""

  if [[ -n "$configured" ]]; then
    if [[ "$configured" = /* ]]; then
      resolved="$configured"
    else
      resolved="$(command -v -- "$configured" 2>/dev/null || true)"
    fi
  else
    resolved="$(command -v -- "$fallback" 2>/dev/null || true)"
  fi

  if [[ -z "$resolved" || ! -x "$resolved" ]]; then
    red "  ❌ missing dependency: $label"
    return 1
  fi

  printf -v "$variable_name" '%s' "$resolved"
  export "$variable_name"
}

resolve_orca_command() {
  local selected=""
  if [[ -n "${ORCA_CLI_COMMAND+x}" ]]; then
    selected="$ORCA_CLI_COMMAND"
    [[ -n "$selected" ]] || {
      red "  ❌ ORCA_CLI_COMMAND is set but empty"
      return 1
    }
    if [[ "$selected" != /* ]]; then
      selected="$(command -v -- "$selected" 2>/dev/null || true)"
    fi
  else
    # The live contract records `orca` as the only supported local fallback.
    selected="$(command -v -- orca 2>/dev/null || true)"
  fi

  if [[ -z "$selected" || ! -x "$selected" ]]; then
    red "  ❌ missing dependency: selected Orca CLI"
    return 1
  fi
  ORCA_CLI_COMMAND="$selected"
  export ORCA_CLI_COMMAND
}

preflight_pyyaml() {
  if ! "$PYTHON_BIN" -c 'import yaml' >/dev/null 2>&1; then
    red "  ❌ missing Python dependency: PyYAML for $PYTHON_BIN"
    red "     Install it with: $PYTHON_BIN -m pip install PyYAML"
    return 1
  fi
}

verify_rtk() {
  if ! "$RTK_BIN" gain >/dev/null 2>&1; then
    fail "RTK_BIN is not the RTK Token Killer executable: rtk gain failed for $RTK_BIN"
    return 1
  fi
}

resolve_rtk_binary() {
  local configured="${RTK_BIN:-}"

  if [[ -n "$configured" ]]; then
    resolve_command RTK_BIN "RTK Token Killer" rtk || return 1
  elif resolve_command RTK_BIN "RTK Token Killer" rtk; then
    :
  else
    resolve_command BREW_BIN "Homebrew" brew || {
      fail "RTK Token Killer is missing; install Homebrew or set RTK_BIN to a valid executable"
      return 1
    }
    cyan "  ⚡ RTK Token Killer not found — installing $RTK_HOMEBREW_FORMULA..."
    if ! "$BREW_BIN" install "$RTK_HOMEBREW_FORMULA"; then
      fail "could not install RTK Token Killer with Homebrew formula $RTK_HOMEBREW_FORMULA"
      return 1
    fi
    resolve_command RTK_BIN "RTK Token Killer" rtk || {
      fail "Homebrew installed $RTK_HOMEBREW_FORMULA, but the rtk executable could not be resolved"
      return 1
    }
  fi

  verify_rtk || return 1
  green "  ✅ verified RTK Token Killer at $RTK_BIN"
}

preflight_rtk() {
  resolve_rtk_binary
}

initialize_rtk_plugin() {
  cyan "  ⚡ initializing the RTK OpenCode plugin..."
  if ! "$RTK_BIN" init -g --opencode --auto-patch; then
    fail "could not initialize the RTK OpenCode plugin"
    return 1
  fi
  if [[ -L "$RTK_PLUGIN_PATH" || ! -f "$RTK_PLUGIN_PATH" ]]; then
    fail "RTK initialization did not create a regular plugin file at $RTK_PLUGIN_PATH"
    return 1
  fi
  green "  ✅ initialized the RTK OpenCode plugin at $RTK_PLUGIN_PATH"
}

preflight_dependencies() {
  local failed=0

  resolve_command WT_BIN "wt" wt || failed=1
  resolve_orca_command || failed=1
  resolve_command OPENCODE_BIN "opencode" opencode || failed=1
  resolve_command BUNX_BIN "bunx" bunx || failed=1
  resolve_command PNPM_BIN "pnpm" pnpm || failed=1
  resolve_command NPM_BIN "npm" npm || failed=1
  resolve_command PYTHON_BIN "Python 3" python3 || failed=1
  preflight_rtk || failed=1
  if [[ -n "${PYTHON_BIN:-}" && -x "${PYTHON_BIN:-}" ]]; then
    preflight_pyyaml || failed=1
  fi


  return "$failed"
}

validate_tracked_worktrunk_config() {
  [[ -f "$WORKTRUNK_CONFIG_SOURCE" ]] || return 1
  [[ "$(grep -Fc '[[post-start]]' "$WORKTRUNK_CONFIG_SOURCE")" -eq 2 ]] || return 1
  grep -Fq 'install-deps = "~/developer/dotfiles/worktree-pnpm-install.sh --workspace-path {{ worktree_path }}"' "$WORKTRUNK_CONFIG_SOURCE" || return 1
  grep -Fq 'worktree-setup = "~/developer/dotfiles/worktree-setup.sh' "$WORKTRUNK_CONFIG_SOURCE" || return 1
}

validate_json_file() {
  local file="$1"
  "$PYTHON_BIN" - "$file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    json.load(handle)
PY
}

normalize_jsonc_file() {
  local file="$1"
  local mode="${2:-validate}"
  "$PYTHON_BIN" - "$file" "$mode" <<'PY'
import json
import sys

source = open(sys.argv[1], encoding="utf-8").read()
mode = sys.argv[2]
output = []
index = 0
in_string = False
escaped = False
while index < len(source):
    char = source[index]
    next_char = source[index + 1] if index + 1 < len(source) else ""
    if in_string:
        output.append(char)
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
        output.append(char)
        index += 1
    elif char == "/" and next_char == "/":
        index += 2
        while index < len(source) and source[index] not in "\r\n":
            index += 1
    elif char == "/" and next_char == "*":
        index += 2
        closed = False
        while index + 1 < len(source) and source[index:index + 2] != "*/":
            index += 1
        if index + 1 < len(source):
            index += 2
            closed = True
        if not closed:
            raise SystemExit("unterminated JSONC block comment")
    else:
        output.append(char)
        index += 1

cleaned = "".join(output)
normalized = []
index = 0
in_string = False
escaped = False
while index < len(cleaned):
    char = cleaned[index]
    if in_string:
        normalized.append(char)
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
        normalized.append(char)
        index += 1
    elif char == ',':
        lookahead = index + 1
        while lookahead < len(cleaned) and cleaned[lookahead].isspace():
            lookahead += 1
        if lookahead < len(cleaned) and cleaned[lookahead] in "}]":
            index += 1
        else:
            normalized.append(char)
            index += 1
    else:
        normalized.append(char)
        index += 1

config = json.loads("".join(normalized))
if mode == "omo":
    plugins = config.get("plugin", [])
    has_omo = isinstance(plugins, list) and any(
        isinstance(plugin, str)
        and plugin == "oh-my-opencode-slim"
        for plugin in plugins
    )
    raise SystemExit(0 if has_omo else 1)
PY
}

validate_jsonc_file() {
  normalize_jsonc_file "$1" validate
}

jsonc_has_omo() {
  normalize_jsonc_file "$1" omo
}

scan_deployment_inputs() {
  "$PYTHON_BIN" - "$@" <<'PY'
import pathlib
import re
import sys

assignment = re.compile(
    r"(?i)(?:api[-_]?key|access[-_]?token|auth[-_]?token|client[-_]?secret|"
    r"password|passwd|credential|secret)\s*[\"']?\s*[:=]\s*[\"']?"
    r"(?P<value>(?!\{(?:env|file):)[^\"'\s,}\]]{4,})"
)
prefix = re.compile(
    r"(?i)\b(?:bearer\s+|ctx7sk-|sk-|gh[pousr]_|github_pat_|xox[baprs]-|"
    r"AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.)[A-Za-z0-9_./+=:-]{16,}"
)
injection_placeholder = re.compile(r"\{(?:env|file):[^}]+\}")
safe_placeholder = re.compile(r"(?i)^(?:your[-_].*|example(?:[-_].*)?|key|token|secret|password|\.\.\.)$")

roots = [pathlib.Path(value) for value in sys.argv[1:]]
candidates = set()
for root in roots:
    if root.is_file():
        candidates.add(root)
    elif root.is_dir():
        candidates.update(candidate for candidate in root.rglob("*") if candidate.is_file())

for path in sorted(candidates):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"unable to inspect deployment asset {path}: {error}", file=sys.stderr)
        raise SystemExit(1)
    masked = injection_placeholder.sub("", text)
    assignment_hit = any(not safe_placeholder.match(match.group("value")) for match in assignment.finditer(masked))
    if assignment_hit or prefix.search(masked):
        print("staged secret-like credential detected in deployment asset", file=sys.stderr)
        raise SystemExit(1)
PY
}

# Centralized manifest/ownership safety helper.
# Only validation and diagnostic paths (validate, compare) are read-only;
# build, adopt, remove, and install are mutating operations managed by the
# deployment script's ordered stages.
manifest_tool() {
  local operation="$1"
  shift
  "$PYTHON_BIN" - "$operation" "$@" <<'PY'
import datetime
import difflib
import errno
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from shutil import copy2


OPERATION = sys.argv[1]
MANIFEST_NAME = ".ai-rules.manifest.json"


def fail(message):
    raise SystemExit(message)


def read_manifest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        fail(f"manifest is not a regular file: {path}")
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        fail(f"malformed manifest {path}: {error}")
    if not isinstance(data, dict):
        fail(f"malformed manifest {path}: top level must be an object")
    return data


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative:
        fail("manifest paths must be non-empty strings")
    if "\x00" in relative or "\\" in relative:
        fail(f"manifest path is not a portable relative path: {relative!r}")
    path = Path(relative)
    if path.is_absolute() or relative.startswith("/"):
        fail(f"manifest path must be relative: {relative!r}")
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        fail(f"manifest path contains an unsafe component: {relative!r}")
    root = Path(root)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        fail(f"OpenCode config path is not a regular directory: {root}")
    root_resolved = root.resolve()
    candidate = root.joinpath(*parts)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        fail(f"manifest path escapes the OpenCode config directory: {relative!r}")

    current = root
    for part in parts:
        current /= part
        if current.is_symlink():
            fail(f"manifest path traverses a symlink: {relative!r}")
    return candidate


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_parts(data, *, require_hashes=True):
    if data.get("managed_by") != "ai-rules/deploy.sh":
        fail("manifest managed_by must be ai-rules/deploy.sh")
    if data.get("version") != 1:
        fail("manifest version must be 1")
    if not isinstance(data.get("timestamp"), str) or not data["timestamp"]:
        fail("manifest timestamp must be a non-empty string")

    files = data.get("managed_files")
    directories = data.get("managed_directories")
    hashes = data.get("managed_file_hashes")
    if not isinstance(files, list) or not all(isinstance(value, str) for value in files):
        fail("manifest managed_files must be a list of strings")
    if not isinstance(directories, list) or not all(
        isinstance(value, str) for value in directories
    ):
        fail("manifest managed_directories must be a list of strings")
    if not isinstance(hashes, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in hashes.items()
    ):
        fail("manifest managed_file_hashes must be an object of strings")
    if len(set(files)) != len(files) or len(set(directories)) != len(directories):
        fail("manifest contains duplicate managed paths")
    if set(files) & set(directories):
        fail("manifest path cannot be both a file and a directory")
    if set(hashes) != set(files):
        fail("manifest file hashes must exactly match managed_files")
    if require_hashes:
        for value in hashes.values():
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                fail("manifest file hashes must be lowercase SHA-256 values")
    return files, directories, hashes


def validate_manifest(manifest_path, root, *, require_present=True):
    data = read_manifest(manifest_path)
    files, directories, hashes = manifest_parts(data)
    root = Path(root)
    for relative in [*files, *directories]:
        candidate = safe_path(root, relative)
        if require_present and not candidate.exists():
            fail(f"manifest managed path is missing: {relative}")
        if candidate.is_symlink():
            fail(f"manifest managed path is a symlink: {relative}")
    if require_present:
        for relative in directories:
            candidate = root.joinpath(*relative.split("/"))
            if not candidate.is_dir():
                fail(f"manifest managed directory is not a directory: {relative}")
        for relative in files:
            candidate = root.joinpath(*relative.split("/"))
            if not candidate.is_file():
                fail(f"manifest managed file is not a regular file: {relative}")
            if hash_file(candidate) != hashes[relative]:
                fail(f"manifest managed file was changed: {relative}")
    return data, files, directories, hashes


def write_manifest(path, files, directories, hashes):
    payload = {
        "managed_by": "ai-rules/deploy.sh",
        "version": 1,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "managed_files": sorted(files),
        "managed_directories": sorted(directories),
        "managed_file_hashes": {key: hashes[key] for key in sorted(hashes)},
    }
    path = Path(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def payload_paths(payload):
    payload = Path(payload)
    if payload.is_symlink() or not payload.is_dir():
        fail(f"staged payload is not a regular directory: {payload}")
    files = []
    directories = []
    for path in sorted(payload.rglob("*")):
        relative = path.relative_to(payload).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            fail(f"staged payload contains a symlink: {relative}")
        if path.is_dir():
            directories.append(relative)
        elif path.is_file():
            files.append(relative)
        else:
            fail(f"staged payload contains an unsupported path: {relative}")
    hashes = {
        relative: hash_file(payload.joinpath(*relative.split("/"))) for relative in files
    }
    return files, directories, hashes


def operation_build(payload, manifest):
    files, directories, hashes = payload_paths(payload)
    write_manifest(manifest, files, directories, hashes)


def ensure_directory(path):
    path = Path(path)
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        fail(f"destination is not a regular directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        fail(f"destination is not a regular directory: {path}")


def operation_install(payload, incoming):
    payload = Path(payload)
    incoming = Path(incoming)
    manifest = payload.joinpath(MANIFEST_NAME)
    _, files, directories, _ = validate_manifest(manifest, payload)
    ensure_directory(incoming)

    for relative in directories:
        ensure_directory(safe_path(incoming, relative))

    for relative in files:
        source = safe_path(payload, relative)
        destination = safe_path(incoming, relative)
        ensure_directory(destination.parent)
        copy2(source, destination)

    copy2(safe_path(payload, MANIFEST_NAME), safe_path(incoming, MANIFEST_NAME))


try:
    if OPERATION == "build":
        operation_build(sys.argv[2], sys.argv[3])
    elif OPERATION == "install":
        operation_install(sys.argv[2], sys.argv[3])
    else:
        fail(f"unknown manifest operation: {OPERATION}")
except (OSError, ValueError) as error:
    fail(str(error))
PY
}

validate_review_pipeline_payload() {
  local payload="$1"
  local canonical_skill="$SRCDIR/.rulesync/skills/$REVIEW_PIPELINE_SKILL/SKILL.md"
  local canonical_registry="$SRCDIR/.rulesync/skills/$REVIEW_PIPELINE_SKILL/pipeline.json"
  local staged_skill="$payload/$REVIEW_PIPELINE_SKILL_PATH"
  local staged_registry="$payload/$REVIEW_PIPELINE_REGISTRY_PATH"

  for path in "$canonical_skill" "$canonical_registry" "$staged_skill" "$staged_registry"; do
    [[ -f "$path" && ! -L "$path" ]] || {
      fail "review-pipeline asset is missing or not a regular file: $path"
      return 1
    }
  done
  cmp -s "$canonical_registry" "$staged_registry" || {
    fail "staged review-pipeline registry differs from canonical source"
    return 1
  }
}

copy_tree() {
  local source="$1"
  local destination="$2"
  mkdir -p "$destination"
  cp -R "$source/." "$destination/"
}

stage_rulesync_output() {
  local output_root="$1"
  local input_root="$STAGE_ROOT/rulesync-input"
  mkdir -p "$output_root"
  mkdir -p "$input_root"
  copy_tree "$SRCDIR/.rulesync" "$input_root/.rulesync"
  cp "$SRCDIR/rulesync.jsonc" "$input_root/rulesync.jsonc"
  # Rulesync rejects empty skill directories. Prune only empty directories in
  # the private copy; the tracked source and all unmanaged user files remain
  # untouched.
  "$PYTHON_BIN" - "$input_root/.rulesync/skills" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
for path in sorted(root.rglob("*"), reverse=True):
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()
PY
  cyan "  🔄 Generating pinned rulesync output in a private staging directory..."
  if ! (
    cd "$input_root"
    "$BUNX_BIN" "$RULESYNC_PACKAGE" generate \
      --targets opencode \
      --input-root "$input_root" \
      --output-roots "$output_root" \
      --delete
  ); then
    return 1
  fi
  # Global Rulesync output includes the OpenCode schema marker. Keep the
  # private deployment payload byte-for-byte aligned with that live output so
  # a global check cannot introduce manifest drift after deployment.
  "$PYTHON_BIN" - "$output_root/opencode.jsonc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
if '"$schema"' not in source:
    if not source.startswith("{\n"):
        raise SystemExit("Rulesync OpenCode output has an unexpected shape")
    source = source.replace(
        "{\n",
        '{\n  "$schema": "https://opencode.ai/config.json",\n',
        1,
    )
    path.write_text(source, encoding="utf-8")
PY
}

build_staged_payload() {
  STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ai-rules-deploy.XXXXXX")"
  STAGE_ROOT="$(cd -P "$STAGE_ROOT" && pwd -P)"
  chmod 700 "$STAGE_ROOT"
  local payload="$STAGE_ROOT/payload"
  local rulesync_output="$STAGE_ROOT/rulesync"

  mkdir -p "$payload"

  stage_rulesync_output "$rulesync_output" || return 1
  [[ -f "$rulesync_output/AGENTS.md" ]] || {
    fail "rulesync did not generate AGENTS.md"
    return 1
  }
  [[ -f "$rulesync_output/opencode.jsonc" ]] || {
    fail "rulesync did not generate opencode.jsonc"
    return 1
  }
  [[ -d "$rulesync_output/.opencode/agents" ]] || {
    fail "rulesync did not generate agents"
    return 1
  }
  [[ -d "$rulesync_output/.opencode/skills" ]] || {
    fail "rulesync did not generate skills"
    return 1
  }

  cp "$SRCDIR/opencode.json" "$payload/opencode.json"
  cp "$SRCDIR/oh-my-opencode-slim.json" "$payload/oh-my-opencode-slim.json"
  cp "$SRCDIR/rulesync.jsonc" "$payload/rulesync.jsonc"
  cp "$rulesync_output/AGENTS.md" "$payload/AGENTS.md"
  cp "$rulesync_output/opencode.jsonc" "$payload/opencode.jsonc"
  copy_tree "$rulesync_output/.opencode/agents" "$payload/agents"
  copy_tree "$rulesync_output/.opencode/skills" "$payload/skills"
  copy_tree "$SRCDIR/.rulesync/oh-my-opencode-slim" "$payload/oh-my-opencode-slim"
  copy_tree "$SRCDIR/.rulesync/commands" "$payload/commands"
  validate_review_pipeline_payload "$payload" || return 1
  manifest_tool build "$payload" "$payload/$OPENCODE_MANIFEST_NAME"

  validate_json_file "$payload/opencode.json" || return 1
  validate_json_file "$payload/oh-my-opencode-slim.json" || return 1
  validate_jsonc_file "$payload/rulesync.jsonc" || return 1
  validate_jsonc_file "$payload/opencode.jsonc" || return 1
  "$PYTHON_BIN" "$SRCDIR/scripts/validate-ai-rules.py" \
    --root "$SRCDIR" --payload "$payload" || return 1
  validate_tracked_worktrunk_config || {
    fail "tracked Worktrunk config is not canonical"
    return 1
  }
  [[ -f "$WT_ORCA_SOURCE" && -x "$WT_ORCA_SOURCE" ]] || {
    fail "tracked wt-orca adapter is missing or not executable"
    return 1
  }
  [[ -f "$WORKTREE_STATE_SOURCE" && -x "$WORKTREE_STATE_SOURCE" ]] || {
    fail "tracked worktree-state helper is missing or not executable"
    return 1
  }
  [[ -f "$WORKTRUNK_INSTALLER" && -x "$WORKTRUNK_INSTALLER" ]] || {
    fail "Worktrunk installer is missing or not executable"
    return 1
  }
  scan_deployment_inputs "$payload" "$WT_ORCA_SOURCE" "$WORKTREE_STATE_SOURCE" \
    "$WORKTRUNK_CONFIG_SOURCE" "$WORKTRUNK_INSTALLER" || return 1
}

omo_installed_version() {
  [[ ! -L "$OH_MY_OPENCODE_SLIM_PACKAGE_JSON" && -f "$OH_MY_OPENCODE_SLIM_PACKAGE_JSON" ]] || return 1
  "$PYTHON_BIN" - "$OH_MY_OPENCODE_SLIM_PACKAGE_JSON" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    package = json.load(handle)
if not isinstance(package, dict) or package.get("name") != "oh-my-opencode-slim":
    raise SystemExit(1)
version = package.get("version")
if not isinstance(version, str) or not version.strip():
    raise SystemExit(1)
print(version)
PY
}

install_omo() {
  local installed_version
  cyan "  ⚡ installing latest ${OH_MY_OPENCODE_SLIM_PACKAGE}..."
  if ! "$BUNX_BIN" "$OH_MY_OPENCODE_SLIM_PACKAGE" install --no-tui --companion=no; then
    fail "could not install ${OH_MY_OPENCODE_SLIM_PACKAGE}"
    return 1
  fi
  installed_version="$(omo_installed_version 2>/dev/null || true)"
  if [[ -z "$installed_version" ]]; then
    fail "could not identify a valid installed oh-my-opencode-slim package"
    return 1
  fi
  green "  ✅ oh-my-opencode-slim ${installed_version} installed (requested package: ${OH_MY_OPENCODE_SLIM_PACKAGE})"
}

write_opencode_transaction_marker() {
  local incoming="$1"
  local rollback_path="$2"
  local phase="${3:-prepared}"
  "$PYTHON_BIN" - "$OPENCODE_TRANSACTION_MARKER" "$OPENDIR" "$incoming" "$rollback_path" "$phase" <<'PY'
import datetime
import json
import os
import stat
import sys
import tempfile

marker, live, incoming, rollback, phase = sys.argv[1:]
directory = os.path.dirname(marker)
current_uid = os.getuid()
directory_stat = os.stat(directory)
if (not stat.S_ISDIR(directory_stat.st_mode) or
        directory_stat.st_uid != current_uid or stat.S_IMODE(directory_stat.st_mode) & 0o022):
    raise SystemExit("OpenCode transaction directory has unsafe ownership or permissions")
if os.path.lexists(live):
    live_stat = os.lstat(live)
    if (stat.S_ISLNK(live_stat.st_mode) or not stat.S_ISDIR(live_stat.st_mode) or
            live_stat.st_uid != current_uid or stat.S_IMODE(live_stat.st_mode) & 0o022):
        raise SystemExit("OpenCode live path has unsafe ownership or permissions")
payload = {
    "live": os.path.abspath(live),
    "incoming": os.path.abspath(incoming),
    "rollback": os.path.abspath(rollback),
    "phase": phase,
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
fd, temporary = tempfile.mkstemp(prefix=".opencode.transaction.", dir=directory)
try:
    os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        fd = None
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, marker)
    temporary = None
    try:
        directory_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        directory_fd = None
    if directory_fd is not None:
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
finally:
    if fd is not None:
        os.close(fd)
    if temporary is not None:
        try:
            os.unlink(temporary)
        except OSError:
            pass
PY
}

remove_opencode_transaction_marker() {
  rm -f "$OPENCODE_TRANSACTION_MARKER" || return 1
  "$PYTHON_BIN" - "$(dirname "$OPENCODE_TRANSACTION_MARKER")" <<'PY'
import os
import sys

directory_fd = os.open(sys.argv[1], os.O_RDONLY)
try:
    os.fsync(directory_fd)
finally:
    os.close(directory_fd)
PY
}

recover_pending_opencode_transaction() {
  # A dangling symlink at the marker path is invisible to `-e`; treat any
  # presence (regular file or symlink) as a pending marker and fail closed
  # before mutation, preserving it for manual inspection.
  [[ -e "$OPENCODE_TRANSACTION_MARKER" || -L "$OPENCODE_TRANSACTION_MARKER" ]] || return 0
  if [[ -L "$OPENCODE_TRANSACTION_MARKER" ]]; then
    red "  ❌ OpenCode transaction marker is a symlink; refusing recovery and preserving it for manual inspection"
    return 1
  fi
  if [[ ! -f "$OPENCODE_TRANSACTION_MARKER" ]]; then
    red "  ❌ OpenCode transaction marker is not a regular file; preserving it for manual inspection"
    return 1
  fi
  "$PYTHON_BIN" - "$OPENCODE_TRANSACTION_MARKER" <<'PY'
import json
import os
import re
import shutil
import stat
import sys

marker = os.path.abspath(sys.argv[1])
try:
    marker_stat = os.stat(marker)
    with open(marker, encoding="utf-8") as handle:
        payload = json.load(handle)
except (OSError, ValueError) as error:
    raise SystemExit(f"unreadable OpenCode transaction marker: {error}")

current_uid = os.getuid()
if marker_stat.st_uid != current_uid or stat.S_IMODE(marker_stat.st_mode) & 0o022:
    raise SystemExit("OpenCode transaction marker has unsafe ownership or permissions")
if not isinstance(payload, dict):
    raise SystemExit("invalid OpenCode transaction marker")

required = ("live", "incoming", "rollback")
if any(not isinstance(payload.get(key), str) for key in required):
    raise SystemExit("invalid OpenCode transaction marker")

marker_parent = os.path.dirname(marker)
paths = {key: os.path.abspath(payload[key]) for key in required}
phase = payload.get("phase")
if not isinstance(phase, str) or phase not in ("prepared", "old_moved", "committed"):
    raise SystemExit("invalid OpenCode transaction phase")
marker_name = os.path.basename(marker)
if not marker_name.endswith(".transaction"):
    raise SystemExit("OpenCode transaction marker has an unexpected name")
live = marker[:-len(".transaction")]
if paths["live"] != live or os.path.basename(live) == "":
    raise SystemExit("OpenCode transaction marker live path is not the exact configured path")
if os.path.dirname(live) != marker_parent:
    raise SystemExit("OpenCode transaction live path escaped its config directory")

incoming_match = re.fullmatch(r"\.opencode\.deploy\.([A-Za-z0-9]+)", os.path.basename(paths["incoming"]))
rollback_match = re.fullmatch(r"\.opencode\.previous\.([A-Za-z0-9]+)", os.path.basename(paths["rollback"]))
if not incoming_match or not rollback_match or incoming_match.group(1) != rollback_match.group(1):
    raise SystemExit("OpenCode transaction generated paths do not match the expected deployment names")
if any(os.path.dirname(value) != marker_parent for value in paths.values()):
    raise SystemExit("OpenCode transaction generated path escaped its config directory")

try:
    parent_stat = os.stat(marker_parent)
except OSError as error:
    raise SystemExit(f"cannot stat OpenCode transaction directory: {error}")
if not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != current_uid or stat.S_IMODE(parent_stat.st_mode) & 0o022:
    raise SystemExit("OpenCode transaction directory has unsafe ownership or permissions")

# Reject colliding or aliased recovery layouts before any mutation so a
# corrupt marker is preserved untouched for manual inspection.
if len(set(paths.values())) != len(paths):
    raise SystemExit("OpenCode transaction marker paths are not pairwise distinct")
if marker in paths.values():
    raise SystemExit("OpenCode transaction marker path collides with a managed path")
real_marker = os.path.realpath(marker)
real_paths = [os.path.realpath(value) for value in paths.values()]
if len(set(real_paths)) != len(real_paths):
    raise SystemExit("OpenCode transaction marker paths alias each other")
if real_marker in set(real_paths):
    raise SystemExit("OpenCode transaction marker path aliases a managed path")

live = paths["live"]
incoming = paths["incoming"]
rollback = paths["rollback"]

def present(path):
    return os.path.lexists(path)

def validate_staged_directory(path):
    if not present(path) or os.path.islink(path) or not os.path.isdir(path):
        raise SystemExit(f"OpenCode transaction staged path is not a regular directory: {path}")
    path_stat = os.stat(path)
    if path_stat.st_uid != current_uid or stat.S_IMODE(path_stat.st_mode) & 0o022:
        raise SystemExit(f"OpenCode transaction staged path has unsafe ownership or permissions: {path}")

def validate_live_directory(path):
    if not present(path) or os.path.islink(path) or not os.path.isdir(path):
        raise SystemExit(f"OpenCode live path is not a regular directory: {path}")
    path_stat = os.stat(path)
    if path_stat.st_uid != current_uid or stat.S_IMODE(path_stat.st_mode) & 0o022:
        raise SystemExit("OpenCode live path has unsafe ownership or permissions")

def remove_staged(path):
    validate_staged_directory(path)
    shutil.rmtree(path)

live_present = present(live)
incoming_present = present(incoming)
rollback_present = present(rollback)
if phase == "prepared":
    if not incoming_present:
        if rollback_present:
            if live_present:
                raise SystemExit("prepared OpenCode transaction has an ambiguous live and rollback layout")
            validate_staged_directory(rollback)
            os.replace(rollback, live)
        elif live_present:
            validate_live_directory(live)
        else:
            raise SystemExit("prepared OpenCode transaction has no surviving deployment directory")
    else:
        if live_present:
            if rollback_present:
                raise SystemExit("prepared OpenCode transaction has an ambiguous live and rollback layout")
            validate_live_directory(live)
            remove_staged(incoming)
        elif rollback_present:
            validate_staged_directory(rollback)
            os.replace(rollback, live)
            remove_staged(incoming)
        else:
            # No live path means the deployment was for a previously absent
            # configuration. Complete that reachable transition instead of
            # deleting the only surviving incoming tree.
            validate_staged_directory(incoming)
            os.replace(incoming, live)
elif phase == "old_moved":
    if not live_present and incoming_present and rollback_present:
        validate_staged_directory(incoming)
        validate_staged_directory(rollback)
        os.replace(rollback, live)
        remove_staged(incoming)
    elif live_present and incoming_present and not rollback_present:
        # Recovery may have restored the old tree before its incoming cleanup
        # completed. The live tree is the only valid survivor in this layout.
        validate_live_directory(live)
        remove_staged(incoming)
    elif live_present and not incoming_present and rollback_present:
        # The live tree may be either the committed replacement or an
        # unrelated/manual survivor. Without the incoming tree there is no
        # proof that the replacement reached the committed phase, so never
        # discard the rollback path automatically.
        raise SystemExit(
            "old_moved OpenCode transaction has live and rollback paths without "
            "incoming; preserving all recovery artifacts for manual recovery"
        )
    elif live_present and not incoming_present and not rollback_present:
        # All generated residue was already cleaned; only marker removal remains.
        validate_live_directory(live)
    else:
        raise SystemExit("old_moved OpenCode transaction has an ambiguous generated path state")
elif phase == "committed":
    if not live_present or incoming_present:
        raise SystemExit("committed OpenCode transaction has an unexpected generated path state")
    validate_live_directory(live)
    if rollback_present:
        remove_staged(rollback)

os.unlink(marker)
directory_fd = os.open(marker_parent, os.O_RDONLY)
try:
    os.fsync(directory_fd)
finally:
    os.close(directory_fd)
PY
}

deployment_failpoint() {
  if [[ "${DEPLOY_FAILPOINT:-}" = "$1" ]]; then
    while :; do
      sleep 1
    done
  fi
}

path_identity() {
  "$PYTHON_BIN" - "$1" <<'PY'
import os
import stat
import sys

path = sys.argv[1]
path_stat = os.lstat(path)
if not stat.S_ISDIR(path_stat.st_mode) or path_stat.st_uid != os.getuid():
    raise SystemExit(1)
print(f"{path_stat.st_dev}:{path_stat.st_ino}")
PY
}

remove_fresh_directory() {
  local path="$1"
  local expected_identity="$2"
  local label="$3"
  local actual_identity=""

  if [[ ! -e "$path" && ! -L "$path" ]]; then
    return 0
  fi
  if [[ -z "$expected_identity" ]]; then
    red "  ❌ refusing to remove $label because its ownership cannot be proven: $path"
    return 1
  fi
  actual_identity="$(path_identity "$path" 2>/dev/null || true)"
  if [[ -z "$actual_identity" || "$actual_identity" != "$expected_identity" ]]; then
    red "  ❌ refusing to remove $label because it is no longer this run's directory: $path"
    return 1
  fi
  if ! rm -rf "$path" || [[ -e "$path" || -L "$path" ]]; then
    red "  ❌ could not remove $label: $path"
    return 1
  fi
}

handle_incoming_validation_failure() {
  local incoming="$1"
  local incoming_identity="$2"
  local reason="$3"

  red "  ❌ $reason"
  if ! remove_fresh_directory "$incoming" "$incoming_identity" "incomplete OpenCode incoming path"; then
    red "  ❌ incoming validation cleanup failed; preserving the path for manual inspection: $incoming"
  fi
  return 1
}

commit_opencode_configuration() {
  local payload="$STAGE_ROOT/payload"
  local parent="$(dirname "$OPENDIR")"
  local incoming=""
  local incoming_name=""
  local token=""
  local incoming_identity=""
  local displaced=""

  # Force mode is a full replacement from the validated staged payload. It
  # intentionally does not read, merge, or preserve unknown live files.
  if ! incoming="$(mktemp -d "$parent/.opencode.deploy.XXXXXX")"; then
    red "  ❌ could not create a unique OpenCode incoming path"
    return 1
  fi
  incoming_name="${incoming##*/}"
  token="${incoming_name#.opencode.deploy.}"
  if [[ "$incoming_name" != .opencode.deploy.* || ! "$token" =~ ^[A-Za-z0-9]+$ ]]; then
    handle_incoming_validation_failure "$incoming" "" "mktemp created an unexpected OpenCode incoming path"
    return 1
  fi
  if ! incoming_identity="$(path_identity "$incoming")"; then
    handle_incoming_validation_failure "$incoming" "" "could not verify ownership of the OpenCode incoming path"
    return 1
  fi
  displaced="$parent/.opencode.previous.$token"
  if [[ -e "$displaced" || -L "$displaced" ]]; then
    handle_incoming_validation_failure "$incoming" "$incoming_identity" \
      "the unique OpenCode displaced path already exists: $displaced"
    return 1
  fi
  OPENCODE_DISPLACED_PATH="$displaced"

  if ! manifest_tool install "$payload" "$incoming"; then
    handle_incoming_validation_failure "$incoming" "$incoming_identity" \
      "could not install or validate the OpenCode incoming manifest"
    return 1
  fi

  if ! {
    validate_json_file "$incoming/$OPENCODE_MANIFEST_NAME"
    validate_json_file "$incoming/opencode.json"
    validate_json_file "$incoming/oh-my-opencode-slim.json"
    validate_jsonc_file "$incoming/opencode.jsonc"
    validate_jsonc_file "$incoming/rulesync.jsonc"
  }; then
    handle_incoming_validation_failure "$incoming" "$incoming_identity" \
      "OpenCode incoming manifest or configuration validation failed"
    return 1
  fi

  # The marker is durable before the live directory is moved. If the process
  # is interrupted, the next deployment recovers these exact paths.
  write_opencode_transaction_marker "$incoming" "$displaced" prepared
  if [[ -e "$OPENDIR" || -L "$OPENDIR" ]]; then
    [[ ! -L "$OPENDIR" && -d "$OPENDIR" ]] || fail "OpenCode config path is not a regular directory"
    "$MV_BIN" "$OPENDIR" "$displaced"
    if ! OPENCODE_DISPLACED_IDENTITY="$(path_identity "$displaced")"; then
      red "  ❌ could not verify ownership of the displaced OpenCode path; transaction artifacts are preserved"
      return 1
    fi
    write_opencode_transaction_marker "$incoming" "$displaced" old_moved
  fi
  deployment_failpoint opencode-after-live-move
  if ! "$MV_BIN" "$incoming" "$OPENDIR"; then
    red "  ❌ OpenCode replacement failed; transaction marker and displaced path are preserved for recovery"
    return 1
  fi
  write_opencode_transaction_marker "$incoming" "$displaced" committed
  deployment_failpoint opencode-after-install
}

finalize_opencode_transaction() {
  local displaced="$OPENCODE_DISPLACED_PATH"

  # Keep both artifacts until the complete deployment succeeds. A cleanup
  # failure leaves the committed marker/path for the next recovery pass.
  if [[ -n "$displaced" ]] && ! remove_fresh_directory \
    "$displaced" "$OPENCODE_DISPLACED_IDENTITY" "the displaced OpenCode path"; then
    red "  ❌ could not remove the displaced OpenCode path; preserving it for recovery"
    return 1
  fi
  if ! remove_opencode_transaction_marker; then
    red "  ❌ transaction marker cleanup failed; preserving the marker for recovery"
    return 1
  fi
}

install_wt_orca() {
  local destination_dir="$(dirname "$WT_ORCA_DESTINATION")"
  local staged="$destination_dir/.wt-orca.stage.$$"
  local state_staged="$destination_dir/.worktree-state.stage.$$"

  if ! mkdir -p "$destination_dir"; then
    rm -f "$staged" "$state_staged"
    return 1
  fi
  if [[ -L "$WT_ORCA_DESTINATION" || ( -e "$WT_ORCA_DESTINATION" && ! -f "$WT_ORCA_DESTINATION" ) ]]; then
    fail "wt-orca destination is not a regular file"
    rm -f "$staged" "$state_staged"
    return 1
  fi

  if ! cp "$WT_ORCA_SOURCE" "$staged" || ! chmod 0755 "$staged" ||
    ! cmp -s "$WT_ORCA_SOURCE" "$staged"; then
    red "  ❌ failed to stage the tracked wt-orca adapter"
    rm -f "$staged" "$state_staged"
    return 1
  fi
  if ! cp "$WORKTREE_STATE_SOURCE" "$state_staged" || ! chmod 0755 "$state_staged" ||
    ! cmp -s "$WORKTREE_STATE_SOURCE" "$state_staged"; then
    red "  ❌ failed to stage the tracked worktree-state helper"
    rm -f "$staged" "$state_staged"
    return 1
  fi
  if ! "$MV_BIN" -f "$staged" "$WT_ORCA_DESTINATION"; then
    red "  ❌ could not install wt-orca"
    rm -f "$staged" "$state_staged"
    return 1
  fi
  if ! "$MV_BIN" -f "$state_staged" "$WORKTREE_STATE_DESTINATION"; then
    red "  ❌ could not install worktree-state helper; force deployment has no cross-component rollback"
    rm -f "$staged" "$state_staged"
    return 1
  fi
  if [[ ! -x "$WT_ORCA_DESTINATION" || ! -x "$WORKTREE_STATE_DESTINATION" ]] ||
    ! cmp -s "$WT_ORCA_SOURCE" "$WT_ORCA_DESTINATION" ||
    ! cmp -s "$WORKTREE_STATE_SOURCE" "$WORKTREE_STATE_DESTINATION"; then
    red "  ❌ installed wt-orca or worktree-state helper differs from the tracked source"
    rm -f "$staged" "$state_staged"
    return 1
  fi
  if ! rm -f "$staged" "$state_staged"; then
    red "  ❌ could not remove wt-orca staging files"
    return 1
  fi
  green "  ✅ installed exact wt-orca adapter and worktree-state helper in $destination_dir"
}

install_worktrunk_config() {
  [[ -x "$WORKTRUNK_INSTALLER" ]] || fail "Worktrunk installer is missing or not executable"
  "$WORKTRUNK_INSTALLER" --config-path "$WORKTRUNK_CONFIG_DESTINATION" --force
  green "  ✅ installed canonical Worktrunk config"
}

run_deploy() {
  echo "⚡ deploy.sh — ai-rules (staged rulesync global)"
  echo ""

  deployment_lock_acquire || fail "could not acquire shared deployment lock"

  # Recovery validation needs Python before the broader dependency preflight;
  # resolving this executable is read-only and happens before recovery or any
  # dependency/configuration mutation.
  resolve_command PYTHON_BIN "Python 3" python3 || fail "Python 3 is required for transaction recovery"

  # Recover a transaction left by an interrupted process before any new
  # dependency or configuration mutation.
  recover_pending_opencode_transaction

  # All executable checks happen before generated configuration mutation.
  yellow "  ⚠️  Preflight/package side effects are outside force replacement recovery: RTK/Homebrew state and OMO package/cache state."
  preflight_dependencies || fail "dependency preflight failed"
  build_staged_payload

  # The staged payload has already been validated before this installer can
  # touch the live OpenCode directory.
  install_omo
  mkdir -p "$(dirname "$OPENDIR")"
  commit_opencode_configuration
  # RTK must initialize against the final force-replaced directory, and the
  # initializer verifies that its plugin is a regular file there.
  initialize_rtk_plugin
  install_wt_orca
  install_worktrunk_config
  finalize_opencode_transaction

  DEPLOY_SUCCEEDED=true
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  ✅ Migration complete."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

run_deploy
