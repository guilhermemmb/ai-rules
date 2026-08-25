#!/usr/bin/env bash
# ~/developer/dotfiles/ai-rules/deploy.sh
#
# Stage and deploy the tracked OpenCode configuration without deleting the live
# configuration before validation succeeds.  Worktrunk and wt-orca are
# installed from the sibling dotfiles directory; Orca runtime state is not a
# deployment input or output.
#
# Usage:
#   ./deploy.sh          — deploy (refresh latest OMO and deploy)
#   ./deploy.sh --check  — dry-run: show what would change
#   ./deploy.sh --force  — reinstall the latest OMO package + deploy
set -euo pipefail
MV_BIN="${MV_BIN:-mv}"

MODE="deploy"
MODEL_PROFILE="default"
FORCE=false

SRCDIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DOTFILES_DIR="$(cd -P "$SRCDIR/.." && pwd -P)"

OPENDIR="${OPENCODE_CONFIG_DIR:-${HOME}/.config/opencode}"
OPENCODE_TRANSACTION_MARKER="${OPENDIR}.transaction"
WORKTRUNK_CONFIG_SOURCE="${WORKTRUNK_CONFIG_SOURCE:-$DOTFILES_DIR/worktrunk/config.toml}"
WORKTRUNK_INSTALLER="${WORKTRUNK_INSTALLER:-$DOTFILES_DIR/worktrunk-install.sh}"
WORKTRUNK_CONFIG_DESTINATION="${WORKTRUNK_CONFIG_DESTINATION:-${HOME}/.config/worktrunk/config.toml}"
WT_ORCA_SOURCE="${WT_ORCA_SOURCE:-$DOTFILES_DIR/wt-orca.sh}"
WT_ORCA_DESTINATION="${WT_ORCA_DESTINATION:-${HOME}/.local/bin/wt-orca}"
WORKTREE_STATE_SOURCE="${WORKTREE_STATE_SOURCE:-$DOTFILES_DIR/worktree-state.sh}"
WORKTREE_STATE_DESTINATION="${WORKTREE_STATE_DESTINATION:-$(dirname "$WT_ORCA_DESTINATION")/worktree-state.sh}"
DEPLOYMENT_LOCK_HELPER="${DEPLOYMENT_LOCK_HELPER:-$DOTFILES_DIR/deployment-lock.sh}"

CODEBASE_MEMORY_MCP_BIN="${CODEBASE_MEMORY_MCP_BIN:-${HOME}/.local/bin/codebase-memory-mcp}"
CODEBASE_MEMORY_MCP_VERSION="0.9.0"
CODEBASE_MEMORY_MCP_INSTALLER_URL="https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/v${CODEBASE_MEMORY_MCP_VERSION}/install.sh"
CODEBASE_MEMORY_MCP_RELEASE_URL="https://github.com/DeusData/codebase-memory-mcp/releases/download/v${CODEBASE_MEMORY_MCP_VERSION}"
# Recorded from the versioned installer used by the current 0.9.0 release.
CODEBASE_MEMORY_MCP_INSTALLER_SHA256="90ef82a3da3336ddc2c3851ad56822067b161856f24cd88cbd405fe423af6a66"

# Rulesync and codebase-memory-mcp are repository-recorded convergence inputs.
# OMO intentionally follows the latest published package instead.
RULESYNC_VERSION="16.2.0"
OH_MY_OPENCODE_SLIM_PACKAGE="oh-my-opencode-slim@latest"
RULESYNC_PACKAGE="rulesync@${RULESYNC_VERSION}"
OPENCODE_PACKAGE_CACHE_DIR="${OPENCODE_PACKAGE_CACHE_DIR:-${HOME}/.cache/opencode/packages}"
OH_MY_OPENCODE_SLIM_PACKAGE_JSON="${OH_MY_OPENCODE_SLIM_PACKAGE_JSON:-$OPENCODE_PACKAGE_CACHE_DIR/oh-my-opencode-slim/node_modules/oh-my-opencode-slim/package.json}"

STAGE_ROOT=""
LIVE_SNAPSHOT=""
LIVE_WAS_PRESENT=false
WT_ORCA_SNAPSHOT=""
WT_ORCA_WAS_PRESENT=false
WORKTREE_STATE_SNAPSHOT=""
WORKTREE_STATE_WAS_PRESENT=false
WORKTRUNK_SNAPSHOT=""
WORKTRUNK_WAS_PRESENT=false
DEPLOY_SUCCEEDED=false

# ── parse args ──
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --model-profile=*)
      MODEL_PROFILE="${1#*=}"
      shift
      ;;
    --help|-h)
      cat <<'EOF'
Usage: ./deploy.sh [--check | --force | --model-profile=<name>]
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

fail() {
  red "  ❌ $1" >&2
  return 1
}

[[ -f "$DEPLOYMENT_LOCK_HELPER" ]] || fail "shared deployment lock helper is missing: $DEPLOYMENT_LOCK_HELPER"
# shellcheck source=/dev/null
source "$DEPLOYMENT_LOCK_HELPER"

cleanup_stage() {
  local exit_code=$?
  local cleanup_failed=false
  if [[ "$DEPLOY_SUCCEEDED" != true && -n "$LIVE_SNAPSHOT" ]]; then
    if [[ -e "$OPENCODE_TRANSACTION_MARKER" ]]; then
      red "  ❌ OpenCode transaction rollback failed; preserving marker and recoverable paths"
      cleanup_failed=true
    elif ! restore_live_configuration; then
      red "  ❌ rollback of the previous OpenCode configuration failed; preserving recovery artifacts"
      cleanup_failed=true
    fi
    if [[ "$cleanup_failed" != true ]] && ! restore_managed_file "$WT_ORCA_DESTINATION" "$WT_ORCA_SNAPSHOT" "$WT_ORCA_WAS_PRESENT"; then
      red "  ❌ rollback of wt-orca failed; preserving recovery artifacts"
      cleanup_failed=true
    fi
    if [[ "$cleanup_failed" != true ]] && ! restore_managed_file "$WORKTREE_STATE_DESTINATION" "$WORKTREE_STATE_SNAPSHOT" "$WORKTREE_STATE_WAS_PRESENT"; then
      red "  ❌ rollback of worktree-state.sh failed; preserving recovery artifacts"
      cleanup_failed=true
    fi
    if [[ "$cleanup_failed" != true ]] && ! restore_managed_file "$WORKTRUNK_CONFIG_DESTINATION" "$WORKTRUNK_SNAPSHOT" "$WORKTRUNK_WAS_PRESENT"; then
      red "  ❌ rollback of the Worktrunk config failed; preserving recovery artifacts"
      cleanup_failed=true
    fi
  fi
  if [[ "$cleanup_failed" = true ]]; then
    exit_code=1
  elif [[ -n "$STAGE_ROOT" && -d "$STAGE_ROOT" ]]; then
    rm -rf "$STAGE_ROOT"
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

install_codebase_memory_mcp() {
  if [[ -x "$CODEBASE_MEMORY_MCP_BIN" ]]; then
    green "  ✅ codebase-memory-mcp already installed — skipping"
    return 0
  fi

  resolve_command CURL_BIN "curl" curl || return 1
  local install_dir
  local installer_file
  local installer_hash
  install_dir="$(dirname "$CODEBASE_MEMORY_MCP_BIN")"
  installer_file="$(mktemp "${TMPDIR:-/tmp}/codebase-memory-installer.XXXXXX")"
  cyan "  ⚡ codebase-memory-mcp not found — installing pinned UI variant..."
  if ! "$CURL_BIN" -fsSL "$CODEBASE_MEMORY_MCP_INSTALLER_URL" -o "$installer_file"; then
    rm -f "$installer_file"
    red "  ❌ codebase-memory-mcp installation failed"
    return 1
  fi
  installer_hash="$(shasum -a 256 "$installer_file" | awk '{print $1}')"
  if [[ "$installer_hash" != "$CODEBASE_MEMORY_MCP_INSTALLER_SHA256" ]]; then
    rm -f "$installer_file"
    red "  ❌ codebase-memory-mcp installer checksum did not match the recorded release"
    return 1
  fi
  chmod 0700 "$installer_file"
  if ! HOME="$HOME" CBM_DOWNLOAD_URL="$CODEBASE_MEMORY_MCP_RELEASE_URL" bash "$installer_file" --ui "--dir=$install_dir"; then
    rm -f "$installer_file"
    red "  ❌ codebase-memory-mcp installation failed"
    return 1
  fi
  rm -f "$installer_file"

  [[ -x "$CODEBASE_MEMORY_MCP_BIN" ]] || {
    red "  ❌ codebase-memory-mcp installation did not create $CODEBASE_MEMORY_MCP_BIN"
    return 1
  }
  if ! "$CODEBASE_MEMORY_MCP_BIN" --version 2>/dev/null | grep -Fq "$CODEBASE_MEMORY_MCP_VERSION"; then
    red "  ❌ installed codebase-memory-mcp version did not match the recorded release"
    return 1
  fi
  green "  ✅ codebase-memory-mcp installed at the pinned release"
}

preflight_dependencies() {
  local check_only="$1"
  local failed=0

  resolve_command WT_BIN "wt" wt || failed=1
  resolve_orca_command || failed=1
  resolve_command OPENCODE_BIN "opencode" opencode || failed=1
  resolve_command BUNX_BIN "bunx" bunx || failed=1
  resolve_command PNPM_BIN "pnpm" pnpm || failed=1
  resolve_command PYTHON_BIN "Python 3" python3 || failed=1

  if [[ -x "$CODEBASE_MEMORY_MCP_BIN" ]]; then
    :
  elif [[ "$check_only" = true ]]; then
    red "  ❌ missing dependency: codebase-memory-mcp at $CODEBASE_MEMORY_MCP_BIN"
    failed=1
  else
    install_codebase_memory_mcp || failed=1
  fi

  return "$failed"
}

validate_tracked_worktrunk_config() {
  [[ -f "$WORKTRUNK_CONFIG_SOURCE" ]] || return 1
  grep -Fq '[[post-start]]' "$WORKTRUNK_CONFIG_SOURCE" || return 1
  grep -Fq 'install-deps = "~/developer/dotfiles/worktree-pnpm-install.sh --workspace-path {{ worktree_path }}"' "$WORKTRUNK_CONFIG_SOURCE" || return 1
  grep -Fq 'worktree-setup = "~/developer/dotfiles/worktree-setup.sh' "$WORKTRUNK_CONFIG_SOURCE" || return 1
  grep -Fq '[pre-remove]' "$WORKTRUNK_CONFIG_SOURCE" || return 1
  grep -Fq 'worktree-cleanup = "bash ~/developer/dotfiles/worktree-cleanup.sh' "$WORKTRUNK_CONFIG_SOURCE" || return 1
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
    raise SystemExit(0 if "oh-my-opencode-slim" in config.get("plugin", []) else 1)
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
    except (OSError, UnicodeDecodeError):
        continue
    masked = injection_placeholder.sub("", text)
    assignment_hit = any(not safe_placeholder.match(match.group("value")) for match in assignment.finditer(masked))
    if assignment_hit or prefix.search(masked):
        print("staged secret-like credential detected in deployment asset", file=sys.stderr)
        raise SystemExit(1)
PY
}

copy_tree() {
  local source="$1"
  local destination="$2"
  mkdir -p "$destination"
  cp -R "$source/." "$destination/"
}

stage_rulesync_output() {
  local output_root="$1"
  mkdir -p "$output_root"
  cyan "  🔄 Generating pinned rulesync output in a private staging directory..."
  if ! (
    cd "$SRCDIR"
    "$BUNX_BIN" "$RULESYNC_PACKAGE" generate \
      --targets opencode \
      --input-root "$SRCDIR" \
      --output-roots "$output_root" \
      --delete
  ); then
    return 1
  fi
}

build_staged_payload() {
  STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ai-rules-deploy.XXXXXX")"
  STAGE_ROOT="$(cd -P "$STAGE_ROOT" && pwd -P)"
  chmod 700 "$STAGE_ROOT"
  local payload="$STAGE_ROOT/payload"
  local profile_stage="$STAGE_ROOT/profile"
  local rulesync_output="$STAGE_ROOT/rulesync"

  mkdir -p "$payload" "$profile_stage"
  cp "$SRCDIR/oh-my-opencode-slim.json" "$profile_stage/oh-my-opencode-slim.json"
  cp -R "$SRCDIR/profiles" "$profile_stage/profiles"
  if ! "$PYTHON_BIN" "$SRCDIR/scripts/apply-model-profile.py" "$profile_stage" "$MODEL_PROFILE" >/dev/null; then
    return 1
  fi

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
  cp "$profile_stage/oh-my-opencode-slim.json" "$payload/oh-my-opencode-slim.json"
  cp "$SRCDIR/rulesync.jsonc" "$payload/rulesync.jsonc"
  cp "$rulesync_output/AGENTS.md" "$payload/AGENTS.md"
  cp "$rulesync_output/opencode.jsonc" "$payload/opencode.jsonc"
  copy_tree "$rulesync_output/.opencode/agents" "$payload/agents"
  copy_tree "$rulesync_output/.opencode/skills" "$payload/skills"
  copy_tree "$SRCDIR/.rulesync/oh-my-opencode-slim" "$payload/oh-my-opencode-slim"
  copy_tree "$SRCDIR/.rulesync/commands" "$payload/commands"

  validate_json_file "$payload/opencode.json" || return 1
  validate_json_file "$payload/oh-my-opencode-slim.json" || return 1
  validate_jsonc_file "$payload/rulesync.jsonc" || return 1
  validate_jsonc_file "$payload/opencode.jsonc" || return 1
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

omo_installed() {
  local candidate
  for candidate in "$OPENDIR/opencode.json" "$OPENDIR/opencode.jsonc"; do
    if [[ -f "$candidate" ]] && jsonc_has_omo "$candidate"; then
      omo_installed_version >/dev/null 2>&1
      return $?
    fi
  done
  return 1
}

install_omo() {
  local installed_version
  if [[ "$FORCE" = true ]]; then
    cyan "  ⚡ reinstalling latest oh-my-opencode-slim..."
  else
    cyan "  ⚡ refreshing latest oh-my-opencode-slim..."
  fi
  if ! "$BUNX_BIN" "$OH_MY_OPENCODE_SLIM_PACKAGE" install; then
    fail "could not install oh-my-opencode-slim@latest"
    return 1
  fi
  installed_version="$(omo_installed_version 2>/dev/null || true)"
  if [[ -z "$installed_version" ]]; then
    fail "could not identify a valid installed oh-my-opencode-slim package"
    return 1
  fi
  green "  ✅ oh-my-opencode-slim ${installed_version} installed from latest"
}

snapshot_file() {
  local source="$1"
  local snapshot="$2"
  local temporary
  if [[ -e "$source" || -L "$source" ]]; then
    [[ ! -L "$source" && -f "$source" ]] || fail "refusing to snapshot a non-regular managed file: $source"
    [[ ! -L "$snapshot" ]] || fail "refusing to replace a snapshot symlink: $snapshot"
    temporary="$snapshot.partial.$$.$RANDOM"
    rm -f "$temporary"
    if ! cp -p "$source" "$temporary" || ! cmp -s "$source" "$temporary"; then
      rm -f "$temporary"
      return 1
    fi
    if ! "$MV_BIN" -f "$temporary" "$snapshot"; then
      rm -f "$temporary"
      return 1
    fi
    printf 'true\n'
  else
    printf 'false\n'
  fi
}

snapshot_directory() {
  local source="$1"
  local snapshot="$2"
  local temporary="$snapshot.partial.$$.$RANDOM"
  local displaced="$snapshot.previous.$$.$RANDOM"

  [[ ! -L "$snapshot" ]] || return 1
  rm -rf "$temporary" "$displaced"
  mkdir -p "$temporary" || return 1
  if ! cp -R "$source/." "$temporary/"; then
    rm -rf "$temporary"
    return 1
  fi

  if [[ -e "$snapshot" ]]; then
    [[ -d "$snapshot" ]] || {
      rm -rf "$temporary"
      return 1
    }
    if ! "$MV_BIN" "$snapshot" "$displaced"; then
      rm -rf "$temporary"
      return 1
    fi
  fi
  if ! "$MV_BIN" "$temporary" "$snapshot"; then
    rm -rf "$temporary"
    if [[ -e "$displaced" ]]; then
      "$MV_BIN" "$displaced" "$snapshot" || return 1
    fi
    return 1
  fi
  [[ ! -e "$displaced" ]] || rm -rf "$displaced"
}

snapshot_live_configuration() {
  local parent
  local live_snapshot
  local live_was_present
  local wt_orca_snapshot
  local worktree_state_snapshot
  local worktrunk_snapshot
  local wt_orca_was_present
  local worktree_state_was_present
  local worktrunk_was_present

  LIVE_SNAPSHOT=""
  WT_ORCA_SNAPSHOT=""
  WORKTREE_STATE_SNAPSHOT=""
  WORKTRUNK_SNAPSHOT=""
  parent="$(dirname "$OPENDIR")"
  mkdir -p "$parent"
  if [[ -e "$OPENDIR" || -L "$OPENDIR" ]]; then
    [[ ! -L "$OPENDIR" && -d "$OPENDIR" ]] || fail "OpenCode config path is not a regular directory"
    live_was_present=true
    live_snapshot="$STAGE_ROOT/live-snapshot"
    snapshot_directory "$OPENDIR" "$live_snapshot" || return 1
  else
    live_was_present=false
    live_snapshot="$STAGE_ROOT/live-snapshot-absent"
  fi
  wt_orca_snapshot="$STAGE_ROOT/wt-orca-snapshot"
  worktree_state_snapshot="$STAGE_ROOT/worktree-state-snapshot"
  worktrunk_snapshot="$STAGE_ROOT/worktrunk-snapshot"
  wt_orca_was_present="$(snapshot_file "$WT_ORCA_DESTINATION" "$wt_orca_snapshot")" || return 1
  worktree_state_was_present="$(snapshot_file "$WORKTREE_STATE_DESTINATION" "$worktree_state_snapshot")" || return 1
  worktrunk_was_present="$(snapshot_file "$WORKTRUNK_CONFIG_DESTINATION" "$worktrunk_snapshot")" || return 1

  LIVE_SNAPSHOT="$live_snapshot"
  LIVE_WAS_PRESENT="$live_was_present"
  WT_ORCA_SNAPSHOT="$wt_orca_snapshot"
  WT_ORCA_WAS_PRESENT="$wt_orca_was_present"
  WORKTREE_STATE_SNAPSHOT="$worktree_state_snapshot"
  WORKTREE_STATE_WAS_PRESENT="$worktree_state_was_present"
  WORKTRUNK_SNAPSHOT="$worktrunk_snapshot"
  WORKTRUNK_WAS_PRESENT="$worktrunk_was_present"
}

restore_managed_file() {
  local destination="$1"
  local snapshot="$2"
  local was_present="$3"
  local parent="$(dirname "$destination")"
  local replacement="$parent/.managed-restore.$$"
  local displaced="$parent/.managed-failed.$$"

  rm -rf "$replacement" "$displaced"
  if [[ "$was_present" = true ]]; then
    mkdir -p "$parent"
    cp -p "$snapshot" "$replacement"
    if [[ -e "$destination" || -L "$destination" ]]; then
      "$MV_BIN" "$destination" "$displaced" || return 1
    fi
    if ! "$MV_BIN" "$replacement" "$destination"; then
      if [[ -e "$displaced" ]]; then
        "$MV_BIN" "$displaced" "$destination" || return 1
      fi
      return 1
    fi
    rm -rf "$displaced" || return 1
  elif [[ -e "$destination" || -L "$destination" ]]; then
    "$MV_BIN" "$destination" "$displaced" || return 1
    rm -rf "$displaced" || return 1
  fi
}

restore_live_configuration() {
  [[ -n "$LIVE_SNAPSHOT" ]] || return 0
  local parent="$(dirname "$OPENDIR")"
  local restore_path="$parent/.opencode.rollback.$$"
  rm -rf "$restore_path"
  if [[ "$LIVE_WAS_PRESENT" = true ]]; then
    mkdir -p "$restore_path"
    cp -R "$LIVE_SNAPSHOT/." "$restore_path/"
    local displaced=false
    if [[ -e "$OPENDIR" || -L "$OPENDIR" ]]; then
      "$MV_BIN" "$OPENDIR" "$parent/.opencode.failed.$$" || return 1
      displaced=true
    fi
    if ! "$MV_BIN" "$restore_path" "$OPENDIR"; then
      if [[ "$displaced" = true ]]; then
        "$MV_BIN" "$parent/.opencode.failed.$$" "$OPENDIR" || return 1
      fi
      return 1
    fi
    if [[ "$displaced" = true ]]; then
      rm -rf "$parent/.opencode.failed.$$" || return 1
    fi
  elif [[ -e "$OPENDIR" || -L "$OPENDIR" ]]; then
    "$MV_BIN" "$OPENDIR" "$parent/.opencode.failed.$$" || return 1
    rm -rf "$parent/.opencode.failed.$$" || return 1
  fi
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
  [[ -e "$OPENCODE_TRANSACTION_MARKER" ]] || return 0
  [[ ! -L "$OPENCODE_TRANSACTION_MARKER" && -f "$OPENCODE_TRANSACTION_MARKER" ]] ||
    fail "OpenCode transaction marker is not a regular file"
  "$PYTHON_BIN" - "$OPENCODE_TRANSACTION_MARKER" <<'PY'
import json
import os
import shutil
import sys

marker = os.path.abspath(sys.argv[1])
with open(marker, encoding="utf-8") as handle:
    payload = json.load(handle)

required = ("live", "incoming", "rollback")
if any(not isinstance(payload.get(key), str) for key in required):
    raise SystemExit("invalid OpenCode transaction marker")

marker_parent = os.path.dirname(marker)
paths = {key: os.path.abspath(payload[key]) for key in required}
phase = payload.get("phase", "prepared")
if phase not in ("prepared", "old_moved", "committed"):
    raise SystemExit("invalid OpenCode transaction phase")
if any(os.path.dirname(value) != marker_parent for value in paths.values()):
    raise SystemExit("OpenCode transaction marker path escaped its config directory")

live = paths["live"]
incoming = paths["incoming"]
rollback = paths["rollback"]

def present(path):
    return os.path.lexists(path)

def remove_staged(path):
    if os.path.islink(path) or not os.path.isdir(path):
        os.unlink(path)
    else:
        shutil.rmtree(path)

if present(live):
    if present(incoming) and present(rollback):
        raise SystemExit("ambiguous OpenCode transaction; refusing recovery")
    if present(incoming):
        remove_staged(incoming)
    elif present(rollback):
        remove_staged(rollback)
elif present(rollback):
    os.replace(rollback, live)
    if present(incoming):
        remove_staged(incoming)
elif present(incoming):
    remove_staged(incoming)
else:
    raise SystemExit("OpenCode transaction has no recoverable paths")

os.unlink(marker)
try:
    directory_fd = os.open(marker_parent, os.O_RDONLY)
except OSError:
    directory_fd = None
if directory_fd is not None:
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

commit_opencode_configuration() {
  local payload="$STAGE_ROOT/payload"
  local parent="$(dirname "$OPENDIR")"
  local incoming="$parent/.opencode.deploy.$$"
  local rollback_path="$parent/.opencode.previous.$$"

  rm -rf "$incoming" "$rollback_path"
  mkdir -p "$incoming"
  if [[ -e "$OPENDIR" ]]; then
    [[ ! -L "$OPENDIR" && -d "$OPENDIR" ]] || fail "OpenCode config path changed to a non-regular directory"
    cp -R "$OPENDIR/." "$incoming/"
  fi

  # Remove only the paths owned by this deployment.  Other OpenCode files are
  # retained in the replacement directory.
  rm -rf "$incoming/oh-my-opencode-slim" "$incoming/commands" \
    "$incoming/agents" "$incoming/skills" "$incoming/.opencode"
  rm -f "$incoming/opencode.json" "$incoming/opencode.jsonc" \
    "$incoming/oh-my-opencode-slim.json" "$incoming/rulesync.jsonc" "$incoming/AGENTS.md"

  cp "$payload/opencode.json" "$incoming/opencode.json"
  cp "$payload/opencode.jsonc" "$incoming/opencode.jsonc"
  cp "$payload/oh-my-opencode-slim.json" "$incoming/oh-my-opencode-slim.json"
  cp "$payload/rulesync.jsonc" "$incoming/rulesync.jsonc"
  cp "$payload/AGENTS.md" "$incoming/AGENTS.md"
  copy_tree "$payload/oh-my-opencode-slim" "$incoming/oh-my-opencode-slim"
  copy_tree "$payload/commands" "$incoming/commands"
  copy_tree "$payload/agents" "$incoming/agents"
  copy_tree "$payload/skills" "$incoming/skills"

  validate_json_file "$incoming/opencode.json"
  validate_json_file "$incoming/oh-my-opencode-slim.json"
  validate_jsonc_file "$incoming/opencode.jsonc"
  validate_jsonc_file "$incoming/rulesync.jsonc"

  write_opencode_transaction_marker "$incoming" "$rollback_path" prepared
  if [[ -e "$OPENDIR" ]]; then
    "$MV_BIN" "$OPENDIR" "$rollback_path"
    write_opencode_transaction_marker "$incoming" "$rollback_path" old_moved
  fi
  deployment_failpoint opencode-after-live-move
  if ! "$MV_BIN" "$incoming" "$OPENDIR"; then
    if [[ -e "$rollback_path" ]]; then
      if "$MV_BIN" "$rollback_path" "$OPENDIR"; then
        remove_opencode_transaction_marker
      else
        red "  ❌ OpenCode rollback restoration failed; transaction marker and recoverable paths are preserved"
        return 1
      fi
    else
      red "  ❌ OpenCode replacement failed without a rollback path; transaction marker is preserved"
      return 1
    fi
    return 1
  fi
  write_opencode_transaction_marker "$incoming" "$rollback_path" committed
  deployment_failpoint opencode-after-install
  rm -rf "$rollback_path"
  if ! remove_opencode_transaction_marker; then
    red "  ❌ OpenCode transaction marker cleanup failed; preserving marker for startup recovery"
    return 1
  fi
}

install_wt_orca() {
  local destination_dir="$(dirname "$WT_ORCA_DESTINATION")"
  local staged="$destination_dir/.wt-orca.stage.$$"
  local state_staged="$destination_dir/.worktree-state.stage.$$"
  mkdir -p "$destination_dir"
  if [[ -L "$WT_ORCA_DESTINATION" || ( -e "$WT_ORCA_DESTINATION" && ! -f "$WT_ORCA_DESTINATION" ) ]]; then
    fail "wt-orca destination is not a regular file"
  fi
  cp "$WT_ORCA_SOURCE" "$staged"
  chmod 0755 "$staged"
  cmp -s "$WT_ORCA_SOURCE" "$staged" || fail "staged wt-orca does not match the tracked adapter"
  cp "$WORKTREE_STATE_SOURCE" "$state_staged"
  chmod 0755 "$state_staged"
  cmp -s "$WORKTREE_STATE_SOURCE" "$state_staged" || fail "staged worktree-state helper does not match the tracked helper"
  "$MV_BIN" -f "$staged" "$WT_ORCA_DESTINATION"
  "$MV_BIN" -f "$state_staged" "$WORKTREE_STATE_DESTINATION"
  [[ -x "$WT_ORCA_DESTINATION" ]] || fail "installed wt-orca is not executable"
  [[ -x "$WORKTREE_STATE_DESTINATION" ]] || fail "installed worktree-state helper is not executable"
  cmp -s "$WT_ORCA_SOURCE" "$WT_ORCA_DESTINATION" || fail "installed wt-orca differs from the tracked adapter"
  cmp -s "$WORKTREE_STATE_SOURCE" "$WORKTREE_STATE_DESTINATION" || fail "installed worktree-state helper differs from the tracked helper"
  green "  ✅ installed exact wt-orca adapter and worktree-state helper in $destination_dir"
}

install_worktrunk_config() {
  [[ -x "$WORKTRUNK_INSTALLER" ]] || fail "Worktrunk installer is missing or not executable"
  "$WORKTRUNK_INSTALLER" --config-path "$WORKTRUNK_CONFIG_DESTINATION" --force
  green "  ✅ installed canonical Worktrunk config"
}

compare_path() {
  local source="$1"
  local destination="$2"
  local label="$3"
  local differences=""

  if [[ ! -e "$source" ]]; then
    if [[ -e "$destination" ]]; then
      DRIFT=1
      red "  ⚠️  STALE: $label"
    fi
  elif [[ ! -e "$destination" ]]; then
    DRIFT=1
    red "  ⚠️  NEW (missing in live): $label"
  elif [[ -d "$source" ]]; then
    differences="$(diff -rq -x .DS_Store "$source" "$destination" 2>&1 || true)"
    if [[ -n "$differences" ]]; then
      DRIFT=1
      red "  ⚠️  DRIFT detected in $label"
      printf '%s\n' "$differences"
    fi
  elif ! cmp -s "$source" "$destination"; then
    DRIFT=1
    red "  ⚠️  CHANGED: $label"
  fi
}

run_check() {
  echo "🔍 Building temporary global deployment to check for drift..."
  echo ""
  DRIFT=0
  if [[ -e "$OPENCODE_TRANSACTION_MARKER" ]]; then
    DRIFT=1
    red "  ⚠️  pending OpenCode deployment transaction requires recovery"
  fi
  preflight_dependencies true || DRIFT=1
  if [[ -z "${PYTHON_BIN:-}" ]] || ! omo_installed; then
    DRIFT=1
    red "  ⚠️  oh-my-opencode-slim package metadata is missing or invalid"
  fi
  if ! build_staged_payload; then
    red "  ⚠️  staged rulesync/OpenCode assets could not be validated"
    DRIFT=1
  else
    local payload="$STAGE_ROOT/payload"
    compare_path "$payload/AGENTS.md" "$OPENDIR/AGENTS.md" ".config/opencode/AGENTS.md"
    compare_path "$payload/opencode.jsonc" "$OPENDIR/opencode.jsonc" ".config/opencode/opencode.jsonc"
    compare_path "$payload/agents" "$OPENDIR/agents" ".config/opencode/agents"
    compare_path "$payload/skills" "$OPENDIR/skills" ".config/opencode/skills"
    compare_path "$payload/opencode.json" "$OPENDIR/opencode.json" ".config/opencode/opencode.json"
    compare_path "$payload/oh-my-opencode-slim.json" "$OPENDIR/oh-my-opencode-slim.json" ".config/opencode/oh-my-opencode-slim.json"
    compare_path "$payload/rulesync.jsonc" "$OPENDIR/rulesync.jsonc" ".config/opencode/rulesync.jsonc"
    compare_path "$payload/oh-my-opencode-slim" "$OPENDIR/oh-my-opencode-slim" ".config/opencode/oh-my-opencode-slim"
    compare_path "$payload/commands" "$OPENDIR/commands" ".config/opencode/commands"
    [[ ! -d "$OPENDIR/.opencode" ]] || {
      DRIFT=1
      red "  ⚠️  STALE local-mode directory found: $OPENDIR/.opencode"
    }
  fi

  compare_path "$WT_ORCA_SOURCE" "$WT_ORCA_DESTINATION" ".local/bin/wt-orca"
  compare_path "$WORKTREE_STATE_SOURCE" "$WORKTREE_STATE_DESTINATION" ".local/bin/worktree-state.sh"
  compare_path "$WORKTRUNK_CONFIG_SOURCE" "$WORKTRUNK_CONFIG_DESTINATION" ".config/worktrunk/config.toml"

  if [[ "$DRIFT" -eq 0 ]]; then
    green "  ✅ Live deployment matches repository."
    return 0
  fi
  echo ""
  echo "Run './deploy.sh' to apply changes."
  return 1
}

run_deploy() {
  echo "⚡ deploy.sh — ai-rules (staged rulesync global)"
  echo ""

  deployment_lock_acquire || fail "could not acquire shared deployment lock"

  # Recover a transaction left by an interrupted process before any new
  # dependency or configuration mutation.
  recover_pending_opencode_transaction

  # All executable checks happen before any generated configuration mutation.
  preflight_dependencies false || fail "dependency preflight failed"
  build_staged_payload
  snapshot_live_configuration

  # Dependency installation is intentionally separate from convergence.  The
  # staged payload has already been validated before this installer can touch
  # the live OpenCode directory.
  install_omo
  commit_opencode_configuration
  install_wt_orca
  install_worktrunk_config

  DEPLOY_SUCCEEDED=true
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  ✅ Migration complete."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

case "$MODE" in
  check)
    run_check
    ;;
  deploy)
    run_deploy
    ;;
esac
