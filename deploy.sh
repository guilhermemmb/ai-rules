#!/usr/bin/env bash
# ~/developer/dotfiles/ai-rules/deploy.sh
#
# Stage and deploy the tracked OpenCode configuration without deleting the live
# configuration before validation succeeds.  Worktrunk and wt-orca are
# installed from the sibling dotfiles directory; Orca runtime state is not a
# deployment input or output.
#
# Usage:
#   ./deploy.sh          — deploy (refresh OMO 2.2.17 and deploy)
#   ./deploy.sh --check  — dry-run: show what would change
#   ./deploy.sh --force  — reinstall the OMO 2.2.17 package, override hash
#                           drift in opencode.json / opencode.jsonc (deploy-only,
#                           no snapshot/rollback backup), + deploy
set -euo pipefail
MV_BIN="${MV_BIN:-mv}"

MODE="deploy"
MODEL_PROFILE="default"
FORCE=false

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

GITNEXUS_VERSION="1.6.5"
GITNEXUS_TARBALL_URL="https://registry.npmjs.org/gitnexus/-/gitnexus-1.6.5.tgz"
# Registry tarball SRI for the pinned GitNexus artifact. The downloaded bytes
# are verified directly before the tarball is passed to npm for installation.
GITNEXUS_INTEGRITY="sha512-xluRjhobdJ0M0IJniTSZompGoZJQdKBQ4AbZ3HfcbNYRR1Z9jebqOi7/IVrHYGdTdW55/lvnnT1n+zYTq4CnyQ=="
GITNEXUS_INSTALL_PREFIX="${GITNEXUS_INSTALL_PREFIX:-${HOME}/.local}"
GITNEXUS_BIN="${GITNEXUS_BIN:-${GITNEXUS_INSTALL_PREFIX}/bin/gitnexus}"
GITNEXUS_ARTIFACT_ROOT=""
GITNEXUS_ARTIFACT=""
SERENA_GIT_SHA="e771adedb5657c07ab890177d2f17df6ce436026"
SERENA_BIN="${SERENA_BIN:-${HOME}/.local/bin/serena}"
SERENA_CONFIG_DIR="${SERENA_CONFIG_DIR:-${HOME}/.serena}"
SERENA_CONFIG_PATH="$SERENA_CONFIG_DIR/serena_config.yml"
RTK_BIN="${RTK_BIN:-}"
RTK_HOMEBREW_FORMULA="rtk-ai/tap/rtk"
RTK_PLUGIN_PATH="${OPENDIR}/plugins/rtk.ts"

# Rulesync is a repository-recorded convergence input.
# OMO is pinned to the repository-recorded 2.2.17 release.
RULESYNC_VERSION="16.2.0"
OH_MY_OPENCODE_SLIM_PACKAGE="oh-my-opencode-slim@2.2.17"
RULESYNC_PACKAGE="rulesync@${RULESYNC_VERSION}"
OPENCODE_PACKAGE_CACHE_DIR="${OPENCODE_PACKAGE_CACHE_DIR:-${HOME}/.cache/opencode/packages}"
OH_MY_OPENCODE_SLIM_PACKAGE_JSON="${OH_MY_OPENCODE_SLIM_PACKAGE_JSON:-$OPENCODE_PACKAGE_CACHE_DIR/oh-my-opencode-slim@latest/node_modules/oh-my-opencode-slim/package.json}"
OH_MY_OPENCODE_SLIM_NODE_MODULES_DIR="$(dirname "$OH_MY_OPENCODE_SLIM_PACKAGE_JSON")/.."
OPENCODE_SDK_PACKAGE_JSON="${OPENCODE_SDK_PACKAGE_JSON:-$OH_MY_OPENCODE_SLIM_NODE_MODULES_DIR/@opencode-ai/sdk/package.json}"
OPENCODE_PLUGIN_PACKAGE_JSON="${OPENCODE_PLUGIN_PACKAGE_JSON:-$OH_MY_OPENCODE_SLIM_NODE_MODULES_DIR/@opencode-ai/plugin/package.json}"
OPENCODE_COMPATIBILITY_EVIDENCE="${OPENCODE_COMPATIBILITY_EVIDENCE:-}"
COMPATIBILITY_STATUS="unverified"

STAGE_ROOT=""
PRIOR_MANIFEST=""
LIVE_SNAPSHOT=""
LIVE_WAS_PRESENT=false
WT_ORCA_SNAPSHOT=""
WT_ORCA_WAS_PRESENT=false
WORKTREE_STATE_SNAPSHOT=""
WORKTREE_STATE_WAS_PRESENT=false
WORKTRUNK_SNAPSHOT=""
WORKTRUNK_WAS_PRESENT=false
DEPLOY_SUCCEEDED=false
SNAPSHOT_COMPLETE=false
FORCE_MUTATION_STARTED=false
RECOVERY_ARTIFACTS_PRESERVED=false

# ── parse args ──
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      shift
      ;;
    --compatibility-check)
      MODE="compatibility"
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
Usage: ./deploy.sh [--check | --compatibility-check | --force | --model-profile=<name>]

  --force  Reinstall the pinned OMO package, override ownership-manifest hash
           drift in only opencode.json and opencode.jsonc, then deploy. Force
           is deploy-only (rejected with --check or --compatibility-check) and
           creates no snapshot or rollback backup, so a later failure may
           require manual recovery. It does not bypass any other structural,
           path-safety, ownership, transaction, or collision check.
EOF
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

if [[ "$FORCE" = true && "$MODE" != "deploy" ]]; then
  printf '\033[31m%s\033[0m\n' "  ❌ --force is a deploy-only operation and cannot be combined with --check or --compatibility-check" >&2
  exit 1
fi

red()   { printf '\033[31m%s\033[0m\n' "$1"; }
green() { printf '\033[32m%s\033[0m\n' "$1"; }
cyan()  { printf '\033[36m%s\033[0m\n' "$1"; }
yellow() { printf '\033[33m%s\033[0m\n' "$1"; }

force_recovery_warning() {
  yellow "  ⚠️  --force changed OpenCode configuration without snapshot or automatic rollback protection."
  yellow "     Affected paths: $OPENDIR and $OPENCODE_MANIFEST_PATH (temporary path: $(dirname "$OPENDIR")/.opencode.removing.$$)."
  yellow "     Manual recovery: inspect the affected paths and restore the prior OpenCode configuration from a trusted backup if deployment fails."
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
  if [[ "$DEPLOY_SUCCEEDED" != true ]] && [[ "$SNAPSHOT_COMPLETE" = true ]]; then
    if ! rollback_deployment; then
      exit_code=1
      RECOVERY_ARTIFACTS_PRESERVED=true
    fi
  fi
  if [[ "$FORCE_MUTATION_STARTED" = true && $exit_code -ne 0 ]]; then
    force_recovery_warning
  fi
  if [[ -n "$GITNEXUS_ARTIFACT_ROOT" && -d "$GITNEXUS_ARTIFACT_ROOT" ]]; then
    if rm -rf "$GITNEXUS_ARTIFACT_ROOT"; then
      GITNEXUS_ARTIFACT_ROOT=""
      GITNEXUS_ARTIFACT=""
    else
      red "  ❌ could not remove GitNexus staging artifacts: $GITNEXUS_ARTIFACT_ROOT"
      exit_code=1
    fi
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

# Attempt every managed restore in reverse deployment/dependency order,
# even if an earlier restore fails.  Aggregate failures and preserve
# rollback artifacts/markers when restoration is incomplete.
rollback_deployment() {
  local rollback_failed=false
  local pending_marker=false

  # Restore in reverse deployment order: last installed first.
  if ! restore_managed_file "$WORKTRUNK_CONFIG_DESTINATION" "$WORKTRUNK_SNAPSHOT" "$WORKTRUNK_WAS_PRESENT"; then
    red "  ❌ rollback of the Worktrunk config failed; preserving recovery artifacts"
    rollback_failed=true
  fi
  if ! restore_managed_file "$WORKTREE_STATE_DESTINATION" "$WORKTREE_STATE_SNAPSHOT" "$WORKTREE_STATE_WAS_PRESENT"; then
    red "  ❌ rollback of worktree-state.sh failed; preserving recovery artifacts"
    rollback_failed=true
  fi
  if ! restore_managed_file "$WT_ORCA_DESTINATION" "$WT_ORCA_SNAPSHOT" "$WT_ORCA_WAS_PRESENT"; then
    red "  ❌ rollback of wt-orca failed; preserving recovery artifacts"
    rollback_failed=true
  fi
  if [[ -e "$OPENCODE_TRANSACTION_MARKER" || -L "$OPENCODE_TRANSACTION_MARKER" ]]; then
    red "  ❌ OpenCode transaction rollback failed; preserving marker and recoverable paths"
    rollback_failed=true
    pending_marker=true
  elif ! restore_live_configuration; then
    red "  ❌ rollback of the previous OpenCode configuration failed; preserving recovery artifacts"
    rollback_failed=true
  fi

  if [[ "$rollback_failed" = true ]]; then
    if [[ "$pending_marker" != true ]]; then
      red "  ❌ one or more rollback operations failed; recovery artifacts are preserved"
    fi
    return 1
  fi
}

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

gitnexus_version_matches() {
  gitnexus_path_is_trusted || return 1
  gitnexus_artifact_is_verified || return 1
  "$GITNEXUS_BIN" --version 2>/dev/null | grep -Eq "(^|[^0-9])${GITNEXUS_VERSION//./\\.}([^0-9]|$)"
}

gitnexus_prefix_is_trusted() {
  "$PYTHON_BIN" - "$GITNEXUS_INSTALL_PREFIX" <<'PY'
import os
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1])
current_uid = os.getuid()
if path.is_symlink():
    raise SystemExit("GitNexus install prefix is a symlink")

existing = path
while not existing.exists():
    parent = existing.parent
    if parent == existing:
        raise SystemExit("GitNexus install prefix has no existing parent")
    existing = parent

for candidate in [existing, *existing.parents]:
    candidate_stat = os.lstat(candidate)
    if candidate in (path, existing) and candidate_stat.st_uid != current_uid:
        raise SystemExit(f"GitNexus install prefix component is not owned by the current user: {candidate}")
    if stat.S_IMODE(candidate_stat.st_mode) & 0o022:
        raise SystemExit(f"GitNexus install prefix component is group- or world-writable: {candidate}")
    if not stat.S_ISDIR(candidate_stat.st_mode):
        raise SystemExit(f"GitNexus install prefix component is not a directory: {candidate}")
PY
}

gitnexus_path_is_trusted() {
  [[ -e "$GITNEXUS_BIN" && -x "$GITNEXUS_BIN" ]] || return 1
  "$PYTHON_BIN" - "$GITNEXUS_BIN" "$GITNEXUS_INSTALL_PREFIX" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
prefix = Path(sys.argv[2]).resolve()
try:
    resolved = path.resolve(strict=True)
except OSError:
    raise SystemExit("GitNexus executable is dangling or cannot be resolved")
if not resolved.is_file() or not os.access(resolved, os.X_OK):
    raise SystemExit("GitNexus executable does not resolve to an executable regular file")
try:
    resolved.relative_to(prefix)
except ValueError:
    raise SystemExit("GitNexus executable resolves outside the expected npm install prefix")
PY
}

prepare_gitnexus_artifact() {
  GITNEXUS_ARTIFACT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/gitnexus-artifact.XXXXXX")" || return 1
  chmod 700 "$GITNEXUS_ARTIFACT_ROOT"
  GITNEXUS_ARTIFACT="$GITNEXUS_ARTIFACT_ROOT/gitnexus-${GITNEXUS_VERSION}.tgz"
  if ! "$PYTHON_BIN" - "$GITNEXUS_TARBALL_URL" "$GITNEXUS_ARTIFACT" <<'PY'
import shutil
import sys
import urllib.request
from pathlib import Path

url, destination = sys.argv[1:]
with urllib.request.urlopen(url, timeout=120) as response, Path(destination).open("xb") as handle:
    shutil.copyfileobj(response, handle)
PY
  then
    red "  ❌ could not download the pinned GitNexus package artifact"
    return 1
  fi
  [[ -f "$GITNEXUS_ARTIFACT" && ! -L "$GITNEXUS_ARTIFACT" ]] || {
    red "  ❌ npm did not produce a regular GitNexus package artifact"
    return 1
  }
  "$PYTHON_BIN" - "$GITNEXUS_ARTIFACT" "$GITNEXUS_INTEGRITY" <<'PY'
import base64
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = sys.argv[2].removeprefix("sha512-")
actual = base64.b64encode(hashlib.sha512(path.read_bytes()).digest()).decode("ascii")
if actual != expected:
    raise SystemExit("GitNexus package artifact does not match the pinned SRI")
PY
}

gitnexus_artifact_is_verified() {
  [[ -n "$GITNEXUS_ARTIFACT" && -f "$GITNEXUS_ARTIFACT" ]] || return 1
  gitnexus_prefix_is_trusted || return 1
  gitnexus_path_is_trusted || return 1
  "$PYTHON_BIN" - "$GITNEXUS_ARTIFACT" "$GITNEXUS_INSTALL_PREFIX" "$GITNEXUS_BIN" "$GITNEXUS_INTEGRITY" <<'PY'
import base64
import hashlib
import json
import os
import stat
import sys
import tarfile
from pathlib import Path

artifact, prefix, executable, expected_sri = sys.argv[1:]
prefix = Path(prefix).resolve()
package_root = prefix / "lib" / "node_modules" / "gitnexus"
current_uid = os.getuid()

def check_regular(path, label):
    info = os.lstat(path)
    if info.st_uid != current_uid or stat.S_IMODE(info.st_mode) & 0o022:
        raise SystemExit(f"{label} has unsafe ownership or permissions: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"{label} is not a regular file: {path}")

actual_sri = base64.b64encode(hashlib.sha512(Path(artifact).read_bytes()).digest()).decode("ascii")
if expected_sri != "sha512-" + actual_sri:
    raise SystemExit("GitNexus package artifact SRI mismatch")

artifact_files = {}
with tarfile.open(artifact, "r:gz") as archive:
    for member in archive.getmembers():
        name = member.name
        if name in ("package", "package/"):
            continue
        if not name.startswith("package/") or "\x00" in name:
            raise SystemExit("GitNexus package artifact contains an unsafe path")
        relative = Path(name.removeprefix("package/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit("GitNexus package artifact contains a path traversal")
        if member.issym() or member.islnk():
            raise SystemExit("GitNexus package artifact contains a symlink")
        if member.isfile():
            extracted = archive.extractfile(member)
            if extracted is None:
                raise SystemExit("GitNexus package artifact member cannot be read")
            artifact_files[relative.as_posix()] = extracted.read()
        elif not member.isdir():
            raise SystemExit("GitNexus package artifact contains an unsupported member")

if not artifact_files or "package.json" not in artifact_files:
    raise SystemExit("GitNexus package artifact has no valid package files")
for relative, expected in artifact_files.items():
    candidate = package_root / relative
    check_regular(candidate, "GitNexus installed package file")
    # GitNexus 1.6.5's native dependency lifecycle scripts regenerate these
    # Makefiles during npm install. All other package bytes remain pinned to the
    # verified tarball; the executable itself is checked exactly below.
    lifecycle_generated = (
        relative.startswith("vendor/node_modules/node-addon-api/")
        and (relative.endswith(".mk") or relative.endswith(".Makefile"))
    )
    if not lifecycle_generated and candidate.read_bytes() != expected:
        raise SystemExit(f"GitNexus installed package bytes differ from the pinned artifact: {relative}")

package = json.loads(artifact_files["package.json"].decode("utf-8"))
bins = package.get("bin")
if isinstance(bins, str):
    bin_target = bins
elif isinstance(bins, dict):
    bin_target = bins.get("gitnexus")
else:
    bin_target = None
if not isinstance(bin_target, str) or not bin_target:
    raise SystemExit("GitNexus package has no gitnexus executable entry")
resolved_executable = Path(executable).resolve(strict=True)
try:
    executable_relative = resolved_executable.relative_to(package_root).as_posix()
except ValueError:
    raise SystemExit("GitNexus executable resolves outside the installed package")
if executable_relative != bin_target.removeprefix("./"):
    raise SystemExit("GitNexus executable is not the package's declared bin target")
check_regular(resolved_executable, "GitNexus executable")
if resolved_executable.read_bytes() != artifact_files.get(executable_relative):
    raise SystemExit("GitNexus executable bytes differ from the pinned artifact")
PY
}

install_gitnexus() {
  gitnexus_prefix_is_trusted || return 1
  prepare_gitnexus_artifact || return 1
  if gitnexus_version_matches; then
    green "  ✅ GitNexus ${GITNEXUS_VERSION} already matches the verified artifact at $GITNEXUS_BIN — skipping"
    return 0
  fi
  if [[ ! -d "$GITNEXUS_INSTALL_PREFIX" ]]; then
    mkdir -p "$GITNEXUS_INSTALL_PREFIX"
    chmod 700 "$GITNEXUS_INSTALL_PREFIX"
  fi
  cyan "  ⚡ installing pinned GitNexus ${GITNEXUS_VERSION}..."
  if ! "$NPM_BIN" install --global --prefix "$GITNEXUS_INSTALL_PREFIX" --no-audit --no-fund "$GITNEXUS_ARTIFACT"; then
    red "  ❌ GitNexus installation failed"
    return 1
  fi

  [[ -x "$GITNEXUS_BIN" ]] || {
    red "  ❌ GitNexus installation did not create $GITNEXUS_BIN"
    return 1
  }
  gitnexus_path_is_trusted || {
    red "  ❌ GitNexus executable is dangling or resolves outside $GITNEXUS_INSTALL_PREFIX"
    return 1
  }
  gitnexus_artifact_is_verified || return 1
  gitnexus_version_matches || {
    red "  ❌ installed GitNexus version did not match ${GITNEXUS_VERSION}"
    return 1
  }
  green "  ✅ GitNexus ${GITNEXUS_VERSION} installed at $GITNEXUS_BIN"
}

serena_source_matches() {
  local tool_dir=""
  tool_dir="$($UV_BIN tool dir 2>/dev/null)" || return 1
  [[ -n "$tool_dir" && -d "$tool_dir/serena-agent" ]] || return 1
  "$PYTHON_BIN" - "$tool_dir/serena-agent" "$SERENA_GIT_SHA" <<'PY'
import json
import re
import sys
from pathlib import Path

tool_root = Path(sys.argv[1]).resolve()
expected_sha = sys.argv[2]

def normalized_name(value):
    return re.sub(r"[-_.]+", "-", value).lower()

candidates = []
for dist_info in tool_root.rglob("*.dist-info"):
    if dist_info.is_symlink() or not dist_info.is_dir():
        continue
    metadata_path = dist_info / "METADATA"
    if metadata_path.is_symlink() or not metadata_path.is_file():
        continue
    try:
        metadata_lines = metadata_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        continue
    names = [
        line.split(":", 1)[1].strip()
        for line in metadata_lines
        if line.lower().startswith("name:")
    ]
    if len(names) == 1 and normalized_name(names[0]) == "serena-agent":
        candidates.append(dist_info)

if len(candidates) != 1:
    raise SystemExit("Serena source metadata is missing or ambiguous")

direct_url_path = candidates[0] / "direct_url.json"
if direct_url_path.is_symlink() or not direct_url_path.is_file():
    raise SystemExit("Serena distribution has no regular direct_url.json")
try:
    with direct_url_path.open(encoding="utf-8") as handle:
        direct_url = json.load(handle)
except (OSError, ValueError) as error:
    raise SystemExit(f"cannot read Serena distribution direct_url.json: {error}")

vcs_info = direct_url.get("vcs_info") if isinstance(direct_url, dict) else None
if not isinstance(vcs_info, dict):
    raise SystemExit("Serena distribution direct_url.json has no VCS metadata")
if vcs_info.get("vcs") != "git" or vcs_info.get("commit_id") != expected_sha:
    raise SystemExit("Serena distribution source commit does not match the pinned commit")
url = direct_url.get("url")
if not isinstance(url, str):
    raise SystemExit("Serena distribution direct_url.json has no source URL")
normalized_url = url.rstrip("/")
if normalized_url.endswith(".git"):
    normalized_url = normalized_url[:-4]
if normalized_url != "https://github.com/oraios/serena":
    raise SystemExit("Serena distribution source URL does not match the pinned repository")
PY
}

serena_dependency_integrity_matches() {
  local tool_dir=""
  tool_dir="$($UV_BIN tool dir 2>/dev/null)" || return 1
  [[ -n "$tool_dir" && -d "$tool_dir/serena-agent" ]] || return 1
  "$PYTHON_BIN" - "$tool_dir/serena-agent" <<'PY'
import base64
import csv
import hashlib
import sys
from pathlib import Path

tool_root = Path(sys.argv[1]).resolve()
record_paths = list(tool_root.rglob("*.dist-info/RECORD"))
if not record_paths:
    raise SystemExit("Serena tool has no wheel RECORD metadata for dependency integrity verification")

for record_path in record_paths:
    site_packages = record_path.parent.parent
    try:
        with record_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
    except (OSError, UnicodeError, csv.Error) as error:
        raise SystemExit(f"cannot read Serena wheel RECORD: {error}")
    for row in rows:
        if len(row) != 3:
            raise SystemExit(f"malformed Serena wheel RECORD entry: {record_path}")
        relative_name, hash_spec, size = row
        if not hash_spec:
            continue
        try:
            algorithm, encoded_digest = hash_spec.split("=", 1)
            digest = base64.urlsafe_b64decode(encoded_digest + "=" * (-len(encoded_digest) % 4))
            hasher = hashlib.new(algorithm)
        except (ValueError, TypeError):
            raise SystemExit(f"unsupported Serena wheel RECORD hash: {hash_spec}")
        raw_candidate = site_packages / relative_name
        if raw_candidate.is_symlink():
            raise SystemExit(f"Serena wheel RECORD path is a symlink: {relative_name}")
        candidate = raw_candidate.resolve(strict=True)
        try:
            candidate.relative_to(tool_root)
        except ValueError:
            raise SystemExit(f"Serena wheel RECORD path escapes its tool environment: {relative_name}")
        if not candidate.is_file():
            raise SystemExit(f"Serena wheel RECORD path is not a regular file: {relative_name}")
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        if hasher.digest() != digest:
            raise SystemExit(f"Serena wheel RECORD hash mismatch: {relative_name}")
PY
}

resolve_serena_executable() {
  local bin_dir=""
  local candidate=""
  local tool_dir=""
  bin_dir="$($UV_BIN tool dir --bin 2>/dev/null)" || {
    red "  ❌ uv could not resolve its tool binary directory"
    return 1
  }
  bin_dir="${bin_dir//$'\n'/}"
  [[ -n "$bin_dir" && -d "$bin_dir" ]] || {
    red "  ❌ uv returned an invalid tool binary directory: $bin_dir"
    return 1
  }
  tool_dir="$($UV_BIN tool dir 2>/dev/null)" || {
    red "  ❌ uv could not resolve its tool directory"
    return 1
  }
  [[ -n "$tool_dir" && -d "$tool_dir/serena-agent" ]] || {
    red "  ❌ uv returned an invalid Serena tool directory: $tool_dir"
    return 1
  }
  for candidate in "$bin_dir/serena" "$bin_dir/serena-agent"; do
    if [[ -x "$candidate" ]] && "$PYTHON_BIN" - "$candidate" "$tool_dir/serena-agent" <<'PY'
import os
import sys
from pathlib import Path

candidate = Path(sys.argv[1])
tool_root = Path(sys.argv[2]).resolve()
try:
    resolved = candidate.resolve(strict=True)
except OSError:
    raise SystemExit(1)
if not resolved.is_file() or not os.access(resolved, os.X_OK):
    raise SystemExit(1)
try:
    resolved.relative_to(tool_root)
except ValueError:
    raise SystemExit(1)
PY
    then
      SERENA_RESOLVED_BIN="$candidate"
      return 0
    fi
  done
  red "  ❌ uv tool bin-dir does not contain a Serena executable inside the uv-managed tool"
  return 1
}

serena_paths_are_trusted() {
  local tool_dir=""
  local bin_dir=""
  tool_dir="$($UV_BIN tool dir 2>/dev/null)" || return 1
  bin_dir="$($UV_BIN tool dir --bin 2>/dev/null)" || return 1
  "$PYTHON_BIN" - "$tool_dir/serena-agent" "$bin_dir" "$SERENA_RESOLVED_BIN" <<'PY'
import os
import stat
import sys
from pathlib import Path

tool_root = Path(sys.argv[1])
bin_dir = Path(sys.argv[2])
resolved_executable = Path(sys.argv[3]).resolve(strict=True)
current_uid = os.getuid()

def check_path(path, label, *, regular=False):
    info = os.lstat(path)
    if info.st_uid != current_uid or stat.S_IMODE(info.st_mode) & 0o022:
        raise SystemExit(f"{label} has unsafe ownership or permissions: {path}")
    if regular and not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"{label} is not a regular file: {path}")
    if not regular and not stat.S_ISDIR(info.st_mode):
        raise SystemExit(f"{label} is not a directory: {path}")

check_path(tool_root, "Serena uv tool root")
check_path(bin_dir, "Serena uv tool binary directory")
check_path(resolved_executable, "Serena uv executable", regular=True)
try:
    resolved_executable.relative_to(tool_root.resolve())
except ValueError:
    raise SystemExit("Serena uv executable resolves outside its tool root")

for path in tool_root.rglob("*"):
    if path.name == "direct_url.json" or (path.parent.name.endswith(".dist-info") and path.name == "RECORD"):
        if path.is_symlink():
            raise SystemExit(f"Serena installation metadata is a symlink: {path}")
        check_path(path, "Serena installation metadata", regular=True)
        check_path(path.parent, "Serena installation metadata directory")
PY
}

serena_install_matches() {
  validate_serena_config || return 1
  [[ -x "$SERENA_BIN" ]] || return 1
  resolve_serena_executable || return 1
  serena_paths_are_trusted || return 1
  serena_source_matches || return 1
  serena_dependency_integrity_matches || return 1
  serena_launcher_matches_resolved || return 1
  "$SERENA_BIN" --version >/dev/null 2>&1
}

serena_launcher_matches_resolved() {
  [[ -x "$SERENA_BIN" && -x "$SERENA_RESOLVED_BIN" ]] || return 1
  "$PYTHON_BIN" - "$SERENA_BIN" "$SERENA_RESOLVED_BIN" <<'PY'
import os
import stat
import sys
from pathlib import Path

launcher = Path(sys.argv[1])
expected = Path(sys.argv[2])
current_uid = os.getuid()
launcher_stat = os.lstat(launcher)
if launcher_stat.st_uid != current_uid:
    raise SystemExit("Serena stable launcher is not owned by the current user")
if not launcher.is_symlink() and stat.S_IMODE(launcher_stat.st_mode) & 0o022:
    raise SystemExit("Serena stable launcher is group- or world-writable")
parent_stat = os.stat(launcher.parent)
if parent_stat.st_uid != current_uid or stat.S_IMODE(parent_stat.st_mode) & 0o022:
    raise SystemExit("Serena stable launcher directory has unsafe ownership or permissions")
try:
    resolved_launcher = launcher.resolve(strict=True)
    resolved_expected = expected.resolve(strict=True)
except OSError:
    raise SystemExit("Serena launcher or uv-managed executable cannot be resolved")
if resolved_launcher != resolved_expected:
    raise SystemExit("Serena stable launcher does not resolve to the uv-managed executable")
PY
}

refresh_serena_launcher() {
  local launcher_dir
  launcher_dir="$(dirname "$SERENA_BIN")"
  mkdir -p "$launcher_dir"
  if [[ "$SERENA_BIN" = "$SERENA_RESOLVED_BIN" ]]; then
    return 0
  fi
  if [[ -L "$SERENA_BIN" ]] && [[ "$(readlink "$SERENA_BIN")" = "$SERENA_RESOLVED_BIN" ]]; then
    return 0
  fi
  if [[ -e "$SERENA_BIN" && ! -L "$SERENA_BIN" ]]; then
    red "  ❌ stable Serena path is occupied by a regular file: $SERENA_BIN"
    return 1
  fi
  ln -sfn "$SERENA_RESOLVED_BIN" "$SERENA_BIN"
}

install_serena() {
  # The mandatory policy must exist before any Serena executable, --version,
  # or uv installation path that may invoke Serena can run.
  ensure_serena_config || return 1
  if serena_install_matches && resolve_serena_executable && refresh_serena_launcher; then
    green "  ✅ Serena pinned source already installed at $SERENA_BIN — skipping"
    return 0
  fi

  cyan "  ⚡ installing Serena from pinned source ${SERENA_GIT_SHA}..."
  if ! "$UV_BIN" tool install --force --python 3.13 \
    --from "git+https://github.com/oraios/serena@${SERENA_GIT_SHA}" \
    serena-agent; then
    red "  ❌ Serena installation failed"
    return 1
  fi
  resolve_serena_executable || return 1
  refresh_serena_launcher || return 1
  serena_install_matches || {
    red "  ❌ installed Serena does not match source ${SERENA_GIT_SHA} or does not respond to --version"
    return 1
  }
  green "  ✅ Serena installed from pinned source at $SERENA_BIN"
}

validate_serena_config() {
  [[ ! -L "$SERENA_CONFIG_PATH" && -f "$SERENA_CONFIG_PATH" ]] || {
    red "  ❌ Serena global configuration is missing or not a regular file: $SERENA_CONFIG_PATH"
    return 1
  }
  "$PYTHON_BIN" - "$SERENA_CONFIG_PATH" <<'PY'
import os
import stat
import sys
import yaml

path = sys.argv[1]
config_path = os.path.abspath(path)
try:
    config_stat = os.stat(config_path)
    parent_stat = os.stat(os.path.dirname(config_path))
except OSError as error:
    raise SystemExit(f"cannot stat Serena global configuration: {error}")
if config_stat.st_uid != os.getuid():
    raise SystemExit("Serena global configuration is not owned by the current user")
if stat.S_IMODE(config_stat.st_mode) != 0o400:
    raise SystemExit("Serena global configuration must be owner-only and read-only")
if parent_stat.st_uid != os.getuid():
    raise SystemExit("Serena config directory is not owned by the current user")
if stat.S_IMODE(parent_stat.st_mode) & 0o022:
    raise SystemExit("Serena config directory is group- or world-writable")
try:
    with open(path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
except (OSError, yaml.YAMLError) as error:
    raise SystemExit(f"invalid Serena global configuration: {error}")

required_tools = {
    "execute_shell_command",
    "create_text_file",
    "replace_string_in_file",
    "apply_patch",
}
if not isinstance(config, dict):
    raise SystemExit("invalid Serena global configuration: top level must be a mapping")
if config.get("read_only") is not True:
    raise SystemExit("Serena global configuration must set read_only: true")
excluded_tools = config.get("excluded_tools")
if not isinstance(excluded_tools, list) or not required_tools.issubset(excluded_tools):
    raise SystemExit(
        "Serena global configuration must exclude execute_shell_command, "
        "create_text_file, replace_string_in_file, and apply_patch"
    )
PY
}

ensure_serena_config() {
  if [[ -e "$SERENA_CONFIG_DIR" || -L "$SERENA_CONFIG_DIR" ]]; then
    [[ ! -L "$SERENA_CONFIG_DIR" && -d "$SERENA_CONFIG_DIR" ]] || {
      red "  ❌ Serena config directory is not a regular directory: $SERENA_CONFIG_DIR"
      return 1
    }
  else
    mkdir -p "$SERENA_CONFIG_DIR"
  fi

  if [[ -e "$SERENA_CONFIG_PATH" || -L "$SERENA_CONFIG_PATH" ]]; then
    if ! validate_serena_config; then
      red "  ❌ Serena global configuration conflicts with the mandatory read-only policy"
      return 1
    fi
    green "  ✅ validated Serena read-only global configuration"
    return 0
  fi

  cat > "$SERENA_CONFIG_PATH" <<'EOF'
read_only: true
excluded_tools:
  - execute_shell_command
  - create_text_file
  - replace_string_in_file
  - apply_patch
EOF
  chmod 0400 "$SERENA_CONFIG_PATH"
  validate_serena_config || return 1
  green "  ✅ created Serena read-only global configuration"
}

preflight_gitnexus_serena() {
  local check_only="$1"
  local gitnexus_ok=true
  if [[ "$check_only" = true ]]; then
    if ! prepare_gitnexus_artifact || ! gitnexus_version_matches; then
      red "  ❌ missing dependency: GitNexus ${GITNEXUS_VERSION} at $GITNEXUS_BIN"
      gitnexus_ok=false
    fi
    if ! validate_serena_config; then
      red "  ❌ missing or invalid Serena read-only global configuration: $SERENA_CONFIG_PATH"
      return 1
    fi
    if ! serena_install_matches; then
      red "  ❌ missing dependency: pinned Serena at $SERENA_BIN"
    fi
    [[ "$gitnexus_ok" = true ]] && serena_install_matches
    return $?
  fi

  install_gitnexus || return 1
  ensure_serena_config || return 1
  install_serena || return 1
  yellow "  ⚠️  Serena transitive dependencies are resolved by uv at install time; wheel RECORD hashes are checked, but no immutable dependency lock is supplied by this command."
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
  local check_only="$1"

  if [[ "$check_only" = true ]]; then
    resolve_command RTK_BIN "RTK Token Killer" rtk || return 1
    verify_rtk || return 1
    return 0
  fi

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
  local check_only="$1"
  local failed=0

  resolve_command WT_BIN "wt" wt || failed=1
  resolve_orca_command || failed=1
  resolve_command OPENCODE_BIN "opencode" opencode || failed=1
  resolve_command BUNX_BIN "bunx" bunx || failed=1
  resolve_command PNPM_BIN "pnpm" pnpm || failed=1
  resolve_command NPM_BIN "npm" npm || failed=1
  resolve_command UV_BIN "uv" uv || failed=1
  resolve_command PYTHON_BIN "Python 3" python3 || failed=1
  preflight_rtk "$check_only" || failed=1
  if [[ -n "${PYTHON_BIN:-}" && -x "${PYTHON_BIN:-}" ]]; then
    preflight_pyyaml || failed=1
  fi

  if [[ -n "${NPM_BIN:-}" && -n "${UV_BIN:-}" && -n "${PYTHON_BIN:-}" ]]; then
    preflight_gitnexus_serena "$check_only" || failed=1
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


def operation_adopt(payload, live, output):
    files, directories, hashes = payload_paths(payload)
    live = Path(live)
    adopted_files = []
    adopted_directories = []
    adopted_hashes = {}
    if live.is_symlink() or (live.exists() and not live.is_dir()):
        fail(f"OpenCode config path is not a regular directory: {live}")
    if live.exists():
        for relative in directories:
            candidate = safe_path(live, relative)
            if candidate.is_dir():
                adopted_directories.append(relative)
        for relative in files:
            candidate = safe_path(live, relative)
            if candidate.is_file() and hash_file(candidate) == hashes[relative]:
                adopted_files.append(relative)
                adopted_hashes[relative] = hashes[relative]
    write_manifest(output, adopted_files, adopted_directories, adopted_hashes)


def operation_remove(root, manifest):
    _, files, directories, _ = validate_manifest(manifest, root, require_present=False)
    root = Path(root)
    for relative in sorted(files, key=lambda value: (value.count("/"), value), reverse=True):
        candidate = safe_path(root, relative)
        if not os.path.lexists(candidate):
            continue
        if candidate.is_symlink() or not candidate.is_file():
            fail(f"refusing to remove non-regular managed file: {relative}")
        candidate.unlink()
    for relative in sorted(
        directories, key=lambda value: (value.count("/"), value), reverse=True
    ):
        candidate = safe_path(root, relative)
        if not os.path.lexists(candidate):
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            fail(f"refusing to remove non-directory managed path: {relative}")
        try:
            candidate.rmdir()
        except OSError as error:
            # Unknown files in a managed directory are intentionally retained,
            # but every failure other than the portable non-empty-directory
            # errors must propagate.
            if error.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                raise


def ensure_directory(root, relative):
    candidate = safe_path(root, relative)
    if candidate.exists():
        if candidate.is_symlink() or not candidate.is_dir():
            fail(f"managed destination is not a regular directory: {relative}")
        return
    candidate.mkdir()


def operation_install(payload, root):
    payload = Path(payload)
    manifest = payload / MANIFEST_NAME
    _, files, directories, _ = validate_manifest(manifest, payload)
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        fail(f"incoming OpenCode config is not a regular directory: {root}")
    for relative in sorted(directories, key=lambda value: (value.count("/"), value)):
        ensure_directory(root, relative)
    for relative in files:
        source = payload.joinpath(*relative.split("/"))
        destination = safe_path(root, relative)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file():
                fail(f"managed destination is not a regular file: {relative}")
        else:
            destination.parent.mkdir(parents=False, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(manifest, root / MANIFEST_NAME)


def operation_compare(payload, live):
    expected = read_manifest(Path(payload) / MANIFEST_NAME)
    actual, files, directories, hashes = validate_manifest(
        Path(live) / MANIFEST_NAME, live
    )
    differences = []
    for key in ("managed_by", "version", "managed_files", "managed_directories", "managed_file_hashes"):
        if actual.get(key) != expected.get(key):
            differences.append(f"manifest {key} differs")
    payload = Path(payload)
    live = Path(live)
    for relative in directories:
        if not safe_path(live, relative).is_dir():
            differences.append(f"missing managed directory: {relative}")
    for relative in files:
        destination = safe_path(live, relative)
        source = payload.joinpath(*relative.split("/"))
        if not destination.is_file() or hash_file(destination) != hash_file(source):
            differences.append(f"managed file differs: {relative}")
    if differences:
        for difference in differences:
            print(difference, file=sys.stderr)
        raise SystemExit(1)


# Mutable-drift paths: exactly these two live config artifacts are treated as
# a policy/reporting concern (reported by the read-only ``drift-report``
# operation and eligible for force override). Every other managed path remains
# strictly validated.
FORCE_EXEMPT_PATHS = ("opencode.json", "opencode.jsonc")


def operation_force(payload_manifest, live_manifest, live_root, plan_output):
    """Force-aware ownership validation.

    Structural manifest checks and path-safety checks remain strict. Only an
    existing regular managed ``opencode.json`` or ``opencode.jsonc`` whose
    content hash differs from the prior manifest may be overridden; any other
    drift, a missing/symlink/non-regular path, or a malformed manifest fails
    closed. Emits a machine-readable override plan and never prints contents.
    """
    expected = read_manifest(payload_manifest)
    expected_files, expected_directories, expected_hashes = manifest_parts(expected)
    files, directories, hashes = manifest_parts(read_manifest(live_manifest))
    root = Path(live_root)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        fail(f"OpenCode config path is not a regular directory: {root}")

    for relative in [*files, *directories]:
        safe_path(root, relative)

    # Force override is narrow: the ownership sets (managed files and managed
    # directories) must match the prior live manifest exactly. Only the content
    # hash of the exempt mutable files may differ; a staged manifest that adds,
    # removes, or reclassifies a managed path (or drops an exempt file that the
    # live manifest still owns) fails closed.
    if set(expected_files) != set(files):
        fail("staged manifest managed_files do not match the prior live manifest")
    if set(expected_directories) != set(directories):
        fail("staged manifest managed_directories do not match the prior live manifest")
    for relative in FORCE_EXEMPT_PATHS:
        if relative in files and relative not in expected_files:
            fail(f"staged manifest is missing exempt managed file: {relative}")

    for relative in directories:
        candidate = root.joinpath(*relative.split("/"))
        if not candidate.exists():
            fail(f"manifest managed path is missing: {relative}")
        if candidate.is_symlink() or not candidate.is_dir():
            fail(f"manifest managed directory is not a directory: {relative}")

    overrides = []
    for relative in files:
        candidate = root.joinpath(*relative.split("/"))
        if not candidate.exists():
            fail(f"manifest managed file is missing: {relative}")
        if candidate.is_symlink():
            fail(f"manifest managed file is a symlink: {relative}")
        if not candidate.is_file():
            fail(f"manifest managed file is not a regular file: {relative}")
        actual_hash = hash_file(candidate)
        if actual_hash != hashes[relative]:
            if relative in FORCE_EXEMPT_PATHS:
                overrides.append(
                    {
                        "path": relative,
                        "expected_sha256": hashes[relative],
                        "actual_sha256": actual_hash,
                        "staged_sha256": expected_hashes[relative],
                    }
                )
            else:
                fail(f"manifest managed file was changed: {relative}")

    plan = {
        "managed_by": "ai-rules/deploy.sh",
        "version": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "force": True,
        "overrides": overrides,
    }
    if plan_output:
        path = Path(plan_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2, sort_keys=True)
            handle.write("\n")
    for override in overrides:
        print(
            f"force override: {override['path']} "
            f"expected_sha256={override['expected_sha256']} "
            f"actual_sha256={override['actual_sha256']} "
            f"staged_sha256={override['staged_sha256']}"
        )


def operation_collisions(payload, previous_manifest, root):
    """Reject payload files that would overwrite unowned (non-managed) files.

    A payload managed file that is not present in the prior manifest but already
    exists in the destination must be refused rather than silently clobbered, so
    unknown user files always survive a replacement.
    """
    expected = read_manifest(Path(payload) / MANIFEST_NAME)
    expected_files, _, _ = manifest_parts(expected)
    prev_files, _, _ = manifest_parts(read_manifest(previous_manifest))
    prev_set = set(prev_files)
    root = Path(root)
    for relative in expected_files:
        if relative in prev_set:
            continue
        candidate = safe_path(root, relative)
        if os.path.lexists(candidate):
            fail(f"refusing to overwrite unowned file: {relative}")


# Mutable-drift diff bounds. A mutable file larger than DRIFT_DIFF_MAX_BYTES or
# with more than DRIFT_DIFF_MAX_LINES newline-separated lines is reported as
# ``oversized``: it is still hashed, but never decoded, split, or diffed. This
# keeps the drift report bounded and deterministic regardless of file size.
DRIFT_DIFF_MAX_BYTES = 1_048_576  # 1 MiB
DRIFT_DIFF_MAX_LINES = 10_000

# Matches a genuine difflib unified-diff hunk header: ``@@ -l,c +l,c @@ ...``.
# Only exact hunk headers are preserved; every content line is redacted.
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")


def file_info(path):
    """Classify one candidate file for the drift report.

    Returns a dict with ``kind`` and, for readable regular files, ``sha256``.
    Only files within DRIFT_DIFF_MAX_BYTES / DRIFT_DIFF_MAX_LINES are decoded
    to UTF-8 ``text``; oversized files are hashed but reported as
    ``oversized``, and undecodable files as ``binary``. The raw text is only
    used internally to build a redacted diff and is never printed.
    """
    path = Path(path)
    if os.path.islink(path):
        return {"kind": "symlink"}
    if not os.path.lexists(path):
        return {"kind": "missing"}
    if not path.is_file():
        return {"kind": "not-regular"}
    try:
        size = path.stat().st_size
    except OSError:
        return {"kind": "unreadable"}
    if size > DRIFT_DIFF_MAX_BYTES:
        try:
            digest = hash_file(path)
        except OSError:
            return {"kind": "unreadable"}
        return {"kind": "oversized", "sha256": digest}
    try:
        data = path.read_bytes()
    except OSError:
        return {"kind": "unreadable"}
    digest = hashlib.sha256(data).hexdigest()
    # The line bound is checked against the raw bytes (newline count) so
    # oversized-by-lines files are never decoded.
    if data.count(b"\n") + 1 > DRIFT_DIFF_MAX_LINES:
        return {"kind": "oversized", "sha256": digest}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"kind": "binary", "sha256": digest}
    return {"kind": "text", "sha256": digest, "text": text}


def redacted_unified_diff(relative, live_text, staged_text):
    """Return a unified diff whose content lines are redacted.

    Only the two generated file headers (lines 0 and 1) and exact hunk headers
    (``@@ -l,c +l,c @@``) remain visible; every actual content line — including
    content that begins with ``---``, ``+++``, or ``@@`` — is reduced to its
    ``+``/``-``/space marker plus ``<redacted>``. No line content (and
    therefore no secret) is ever emitted.
    """
    live_lines = live_text.splitlines()
    staged_lines = staged_text.splitlines()
    lines = difflib.unified_diff(
        live_lines,
        staged_lines,
        fromfile=f"{relative} (live)",
        tofile=f"{relative} (staged)",
        lineterm="\n",
    )
    redacted = []
    for index, line in enumerate(lines):
        if index < 2:
            # The two generated file headers carry only the relative path and
            # side label, never file content.
            redacted.append(line.rstrip("\n"))
        elif HUNK_HEADER.match(line):
            # A genuine hunk header; preserve its line/count structure only.
            redacted.append(line.rstrip("\n"))
        elif line.startswith(("+", "-", " ")):
            redacted.append(line[0] + "<redacted>")
        else:
            # e.g. "\ No newline at end of file" or any unexpected line.
            redacted.append("<redacted>")
    return "\n".join(redacted)


def drift_entry(relative, live, staged):
    entry = {
        "path": relative,
        "live_sha256": live.get("sha256"),
        "staged_sha256": staged.get("sha256"),
    }
    if live.get("kind") == "text" and staged.get("kind") == "text":
        if live["sha256"] == staged["sha256"]:
            entry["status"] = "identical"
            entry["diff"] = None
        else:
            entry["status"] = "changed"
            entry["diff"] = redacted_unified_diff(relative, live["text"], staged["text"])
        return entry

    kinds = {live.get("kind"), staged.get("kind")}
    if "unreadable" in kinds:
        entry["status"] = "unreadable"
    elif "oversized" in kinds:
        entry["status"] = "oversized"
    elif "binary" in kinds:
        entry["status"] = "binary"
    elif live.get("kind") == "missing":
        entry["status"] = (
            "both-missing" if staged.get("kind") == "missing" else "missing-live"
        )
    elif staged.get("kind") == "missing":
        entry["status"] = "missing-staged"
    elif "symlink" in kinds:
        entry["status"] = "symlink"
    elif "not-regular" in kinds:
        entry["status"] = "not-regular"
    else:
        entry["status"] = "unknown"
    entry["diff"] = None
    return entry


def operation_drift_report(staged_root, live_root):
    """Deterministic, read-only drift report for the mutable live config files.

    For each mutable-drift path the report emits the path, live and staged
    SHA-256, a status, and — only when both sides are safely readable UTF-8
    text within the diff bounds — a redacted unified diff. Binary, oversized,
    unreadable, missing, symlink, and non-regular paths report status and
    hashes only. No file contents or secrets are ever emitted.
    """
    staged_root = Path(staged_root)
    live_root = Path(live_root)
    for root, label in ((staged_root, "staged"), (live_root, "live")):
        if root.is_symlink() or not root.is_dir():
            fail(f"{label} root is not a regular directory: {root}")

    entries = []
    for relative in FORCE_EXEMPT_PATHS:
        staged = file_info(staged_root / relative)
        live = file_info(live_root / relative)
        entries.append(drift_entry(relative, live, staged))

    report = {
        "managed_by": "ai-rules/deploy.sh",
        "operation": "drift-report",
        "mutable_drift_paths": list(FORCE_EXEMPT_PATHS),
        "entries": entries,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


try:
    if OPERATION == "build":
        operation_build(sys.argv[2], sys.argv[3])
    elif OPERATION == "adopt":
        operation_adopt(sys.argv[2], sys.argv[3], sys.argv[4])
    elif OPERATION == "validate":
        validate_manifest(sys.argv[2], sys.argv[3])
    elif OPERATION == "remove":
        operation_remove(sys.argv[2], sys.argv[3])
    elif OPERATION == "install":
        operation_install(sys.argv[2], sys.argv[3])
    elif OPERATION == "compare":
        operation_compare(sys.argv[2], sys.argv[3])
    elif OPERATION == "force":
        operation_force(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif OPERATION == "collisions":
        operation_collisions(sys.argv[2], sys.argv[3], sys.argv[4])
    elif OPERATION == "drift-report":
        operation_drift_report(sys.argv[2], sys.argv[3])
    else:
        fail(f"unknown manifest operation: {OPERATION}")
except (OSError, ValueError) as error:
    fail(str(error))
PY
}

# ── force-deployment helpers ─────────────────────────────────────────
# Force mode lives entirely in deploy.sh and only relaxes hash drift for the
# two mutable usage/config artifacts opencode.json and opencode.jsonc. Every
# other structural, path-safety, ownership, transaction, and collision check
# remains strict and fail-closed.

manifest_override_plan() {
  # Run the force-aware manifest validation. Reads the staged payload manifest,
  # the prior live manifest, and the prior live root; writes a JSON override
  # plan (or fails closed on any structural/non-exempt problem).
  local payload="$1"
  local previous_manifest="$2"
  local previous_root="$3"
  local plan_output="$4"
  manifest_tool force "$payload/$OPENCODE_MANIFEST_NAME" "$previous_manifest" "$previous_root" "$plan_output"
}

preflight_force_summary() {
  # Print a read-only drift summary for the two mutable files via the
  # manifest_tool drift-report operation. Hash/status only, plus a redacted
  # unified diff (structure only, no content) when both sides are safely
  # readable UTF-8 text within the diff bounds. Never prints file contents or
  # secrets.
  local payload="$1"
  local previous_root="$2"
  local report_file=""

  echo ""
  echo "🔍 Force override preflight — mutable usage/config artifacts"
  report_file="$(mktemp "${TMPDIR:-/tmp}/force-drift.XXXXXX")" || {
    yellow "  ⚠️  mutable-drift summary is unavailable"
    echo ""
    return 0
  }
  if ! manifest_tool drift-report "$payload" "$previous_root" > "$report_file" 2>/dev/null; then
    yellow "  ⚠️  mutable-drift summary is unavailable"
    rm -f "$report_file"
    echo ""
    return 0
  fi
  "$PYTHON_BIN" - "$report_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    report = json.load(handle)
for entry in report.get("entries", []):
    path = entry.get("path")
    live_sha = entry.get("live_sha256") or "<none>"
    staged_sha = entry.get("staged_sha256") or "<none>"
    status = entry.get("status", "unknown")
    print(f"     {path}: live={live_sha} staged={staged_sha} status={status}")
    diff = entry.get("diff")
    if diff:
        print(diff)
PY
  rm -f "$report_file"
  echo ""
}

capture_prior_manifest() {
  # Capture the prior ownership manifest so force override runs against a
  # stable prior state before any snapshot mutation. The manifest must be a
  # regular file: a symlink is refused (never dereferenced) so force mode fails
  # closed exactly like strict validation. On a manifestless migration there is
  # nothing to override, so nothing is captured; commit_opencode_configuration
  # adopts instead.
  local prior="$STAGE_ROOT/prior-manifest.json"
  PRIOR_MANIFEST=""
  [[ ! -L "$OPENCODE_MANIFEST_PATH" && -f "$OPENCODE_MANIFEST_PATH" ]] || {
    fail "ownership manifest is not a regular file: $OPENCODE_MANIFEST_PATH"
    return 1
  }
  cp "$OPENCODE_MANIFEST_PATH" "$prior" || return 1
  PRIOR_MANIFEST="$prior"
}

detect_reviewer_shadow() {
  local canonical="$1"
  local shadow
  [[ -f "$canonical" ]] || return 0
  for shadow in \
    "$HOME/.agents/skills/reviewer/SKILL.md" \
    "$HOME/.agents/skills/reviewer.md" \
    "$HOME/.agents/skills/reviewer/SKILL.mdx"; do
    if [[ -L "$shadow" || -e "$shadow" && ! -f "$shadow" ]]; then
      red "  ❌ reviewer shadow entry is not a regular file: $shadow"
      return 1
    fi
    if [[ -f "$shadow" ]] && ! cmp -s "$canonical" "$shadow"; then
      red "  ❌ reviewer shadow skill differs from canonical OpenCode skill: $shadow"
      red "     Reconcile or remove it manually; deploy.sh will not delete it."
      return 1
    fi
  done
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
  manifest_tool build "$payload" "$payload/$OPENCODE_MANIFEST_NAME"

  validate_json_file "$payload/opencode.json" || return 1
  validate_json_file "$payload/oh-my-opencode-slim.json" || return 1
  validate_jsonc_file "$payload/rulesync.jsonc" || return 1
  validate_jsonc_file "$payload/opencode.jsonc" || return 1
  "$PYTHON_BIN" "$SRCDIR/scripts/validate-ai-rules.py" \
    --root "$SRCDIR" --payload "$payload" --profile "$MODEL_PROFILE" || return 1
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

read_package_metadata() {
  local package_json="$1"
  local expected_name="$2"
  "$PYTHON_BIN" - "$package_json" "$expected_name" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected_name = sys.argv[2]
expected_names = {
    "oh-my-opencode-slim",
    "@opencode-ai/sdk",
    "@opencode-ai/plugin",
}
if expected_name not in expected_names:
    raise SystemExit(1)
if path.is_symlink() or not path.is_file():
    raise SystemExit(1)
with path.open(encoding="utf-8") as handle:
    package = json.load(handle)
if not isinstance(package, dict):
    raise SystemExit(1)
name = package.get("name")
version = package.get("version")
if name != expected_name or not isinstance(version, str) or not version.strip():
    raise SystemExit(1)
print(f"name={name}")
print(f"version={version}")
if expected_name == "oh-my-opencode-slim":
    dependencies = package.get("dependencies")
    sdk_range = dependencies.get("@opencode-ai/sdk") if isinstance(dependencies, dict) else None
    if isinstance(sdk_range, str):
        print(f"sdk_dependency={sdk_range}")
PY
}

read_compatibility_evidence() {
  local evidence_path="$1"
  "$PYTHON_BIN" - "$evidence_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if path.is_symlink() or not path.is_file():
    raise SystemExit(1)
with path.open(encoding="utf-8") as handle:
    evidence = json.load(handle)
if not isinstance(evidence, dict):
    raise SystemExit(1)
for key in ("opencode_version", "omo_version", "plugin_version", "sdk_version"):
    value = evidence.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(1)
    print(f"{key}={value.strip()}")
PY
}

preflight_compatibility() {
  local host_version=""
  local installed_omo_version=""
  local installed_sdk_version=""
  local installed_plugin_version=""
  local version_skew=false
  local omo_metadata=""
  local sdk_metadata=""
  local plugin_metadata=""
  local evidence=""
  local evidence_host=""
  local evidence_omo=""
  local evidence_plugin=""
  local evidence_sdk=""
  local key=""
  local value=""

  COMPATIBILITY_STATUS="unverified"
  cyan "  🔎 OpenCode/OMO compatibility diagnostics (read-only)..."
  if host_version="$("$OPENCODE_BIN" --version 2>/dev/null)"; then
    host_version="${host_version//$'\n'/ }"
    printf '     OpenCode host version: %s\n' "$host_version"
  else
    yellow "  ⚠️  could not read installed OpenCode --version"
  fi

  printf '     OMO package requested by source: %s\n' "$OH_MY_OPENCODE_SLIM_PACKAGE"
  if omo_metadata="$(read_package_metadata "$OH_MY_OPENCODE_SLIM_PACKAGE_JSON" "oh-my-opencode-slim" 2>/dev/null)"; then
    while IFS= read -r value; do
      printf '     OMO package metadata: %s\n' "$value"
      case "$value" in
        version=*) installed_omo_version="${value#version=}" ;;
      esac
    done <<< "$omo_metadata"
  else
    yellow "  ⚠️  installed OMO package metadata is unavailable: $OH_MY_OPENCODE_SLIM_PACKAGE_JSON"
  fi

  if sdk_metadata="$(read_package_metadata "$OPENCODE_SDK_PACKAGE_JSON" "@opencode-ai/sdk" 2>/dev/null)"; then
    while IFS= read -r value; do
      printf '     SDK package metadata: %s\n' "$value"
      case "$value" in
        version=*) installed_sdk_version="${value#version=}" ;;
      esac
    done <<< "$sdk_metadata"
  else
    yellow "  ⚠️  installed @opencode-ai/sdk metadata is unavailable: $OPENCODE_SDK_PACKAGE_JSON"
  fi

  if plugin_metadata="$(read_package_metadata "$OPENCODE_PLUGIN_PACKAGE_JSON" "@opencode-ai/plugin" 2>/dev/null)"; then
    while IFS= read -r value; do
      printf '     OpenCode plugin metadata: %s\n' "$value"
      case "$value" in
        version=*) installed_plugin_version="${value#version=}" ;;
      esac
    done <<< "$plugin_metadata"
  else
    yellow "  ⚠️  installed @opencode-ai/plugin metadata is unavailable: $OPENCODE_PLUGIN_PACKAGE_JSON"
  fi

  if [[ -n "$installed_omo_version" && "$installed_omo_version" != "${OH_MY_OPENCODE_SLIM_PACKAGE##*@}" ]]; then
    version_skew=true
    yellow "  ⚠️  version skew: source requests OMO ${OH_MY_OPENCODE_SLIM_PACKAGE##*@}, installed OMO $installed_omo_version"
  fi
  if [[ -n "$installed_plugin_version" && -n "$installed_sdk_version" && "$installed_plugin_version" != "$installed_sdk_version" ]]; then
    version_skew=true
    yellow "  ⚠️  plugin/SDK versions differ: plugin $installed_plugin_version, SDK $installed_sdk_version"
  fi

  if [[ -n "$OPENCODE_COMPATIBILITY_EVIDENCE" ]]; then
    if evidence="$(read_compatibility_evidence "$OPENCODE_COMPATIBILITY_EVIDENCE" 2>/dev/null)"; then
      while IFS='=' read -r key value; do
        case "$key" in
          opencode_version) evidence_host="$value" ;;
          omo_version) evidence_omo="$value" ;;
          plugin_version) evidence_plugin="$value" ;;
          sdk_version) evidence_sdk="$value" ;;
        esac
      done <<< "$evidence"
      if [[ "$version_skew" = false && "$host_version" = "$evidence_host" && "$installed_omo_version" = "$evidence_omo" && "$installed_plugin_version" = "$evidence_plugin" && "$installed_sdk_version" = "$evidence_sdk" ]]; then
        COMPATIBILITY_STATUS="matched"
        green "  ✅ installed host/OMO/plugin/SDK versions match supplied compatibility evidence"
      else
        COMPATIBILITY_STATUS="skew"
        yellow "  ⚠️  installed OpenCode/OMO/plugin/SDK versions differ from supplied compatibility evidence"
        yellow "     Evidence: OpenCode=$evidence_host OMO=$evidence_omo plugin=$evidence_plugin SDK=$evidence_sdk"
      fi
    else
      yellow "  ⚠️  compatibility evidence is missing, malformed, or not a regular file: $OPENCODE_COMPATIBILITY_EVIDENCE"
    fi
  else
    yellow "  ⚠️  no verified compatibility evidence supplied; static checks cannot claim runtime Healthy"
  fi
  printf '     Agent output paths: OpenCode-supported ~/ glob syntax with dedicated allowlists; broad filesystem writes remain denied.\n'
  cyan "     Runtime smoke evidence is still required after a fresh OpenCode restart."
  printf 'COMPATIBILITY_STATUS=%s\n' "$COMPATIBILITY_STATUS"
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
    cyan "  ⚡ reinstalling oh-my-opencode-slim@2.2.17..."
  else
    cyan "  ⚡ refreshing oh-my-opencode-slim@2.2.17..."
  fi
  if ! "$BUNX_BIN" "$OH_MY_OPENCODE_SLIM_PACKAGE" install; then
    fail "could not install oh-my-opencode-slim@2.2.17"
    return 1
  fi
  installed_version="$(omo_installed_version 2>/dev/null || true)"
  if [[ -z "$installed_version" ]]; then
    fail "could not identify a valid installed oh-my-opencode-slim package"
    return 1
  fi
  green "  ✅ oh-my-opencode-slim ${installed_version} installed (pinned package: 2.2.17)"
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
  wt_orca_snapshot="$STAGE_ROOT/wt-orca-snapshot"
  worktree_state_snapshot="$STAGE_ROOT/worktree-state-snapshot"
  worktrunk_snapshot="$STAGE_ROOT/worktrunk-snapshot"
  # Complete all auxiliary snapshots before taking the OpenCode snapshot. The
  # live OpenCode tree is not considered recoverable until every snapshot has
  # succeeded, so an auxiliary failure cannot strand a moved live tree.
  wt_orca_was_present="$(snapshot_file "$WT_ORCA_DESTINATION" "$wt_orca_snapshot")" || return 1
  worktree_state_was_present="$(snapshot_file "$WORKTREE_STATE_DESTINATION" "$worktree_state_snapshot")" || return 1
  worktrunk_was_present="$(snapshot_file "$WORKTRUNK_CONFIG_DESTINATION" "$worktrunk_snapshot")" || return 1

  if [[ -e "$OPENDIR" || -L "$OPENDIR" ]]; then
    [[ ! -L "$OPENDIR" && -d "$OPENDIR" ]] || fail "OpenCode config path is not a regular directory"
    live_was_present=true
    live_snapshot="$STAGE_ROOT/live-snapshot"
    snapshot_directory "$OPENDIR" "$live_snapshot" || return 1
  else
    live_was_present=false
    live_snapshot="$STAGE_ROOT/live-snapshot-absent"
  fi

  LIVE_SNAPSHOT="$live_snapshot"
  LIVE_WAS_PRESENT="$live_was_present"
  WT_ORCA_SNAPSHOT="$wt_orca_snapshot"
  WT_ORCA_WAS_PRESENT="$wt_orca_was_present"
  WORKTREE_STATE_SNAPSHOT="$worktree_state_snapshot"
  WORKTREE_STATE_WAS_PRESENT="$worktree_state_was_present"
  WORKTRUNK_SNAPSHOT="$worktrunk_snapshot"
  WORKTRUNK_WAS_PRESENT="$worktrunk_was_present"
  SNAPSHOT_COMPLETE=true
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
    if [[ ! -d "$LIVE_SNAPSHOT" ]]; then
      red "  ❌ OpenCode live snapshot is missing; leaving live configuration intact"
      return 1
    fi
    mkdir -p "$restore_path"
    if ! cp -R "$LIVE_SNAPSHOT/." "$restore_path/"; then
      rm -rf "$restore_path"
      red "  ❌ OpenCode restore preparation failed; leaving live configuration intact"
      return 1
    fi
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

incoming_match = re.fullmatch(r"\.opencode\.deploy\.(\d+)", os.path.basename(paths["incoming"]))
rollback_match = re.fullmatch(r"\.opencode\.previous\.(\d+)", os.path.basename(paths["rollback"]))
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

replace_live_configuration_force() {
  # Force mode replaces the live OpenCode configuration atomically without
  # retaining any rollback backup state. No transaction marker or rollback
  # directory is created. On failure there is no automatic rollback: the
  # previous configuration is restored best-effort, and manual recovery is
  # reported when that restore also fails.
  local incoming="$1"
  local parent="$(dirname "$OPENDIR")"
  local displaced="$parent/.opencode.removing.$$"

  rm -rf "$displaced"
  if [[ -e "$OPENDIR" || -L "$OPENDIR" ]]; then
    if ! "$MV_BIN" "$OPENDIR" "$displaced"; then
      red "  ❌ could not move the current OpenCode configuration aside; no automatic rollback is available; recover manually"
      return 1
    fi
    if ! "$MV_BIN" "$incoming" "$OPENDIR"; then
      if "$MV_BIN" "$displaced" "$OPENDIR"; then
        red "  ❌ OpenCode replacement failed; the previous configuration was restored"
      else
        red "  ❌ OpenCode replacement failed and the previous configuration could not be restored; manual recovery is required"
      fi
      return 1
    fi
    FORCE_MUTATION_STARTED=true
    force_recovery_warning
    rm -rf "$displaced"
  else
    if ! "$MV_BIN" "$incoming" "$OPENDIR"; then
      red "  ❌ OpenCode replacement failed; no automatic rollback is available; recover manually"
      return 1
    fi
    FORCE_MUTATION_STARTED=true
    force_recovery_warning
  fi
}

commit_opencode_configuration() {
  local payload="$STAGE_ROOT/payload"
  local parent="$(dirname "$OPENDIR")"
  local incoming="$parent/.opencode.deploy.$$"
  local rollback_path="$parent/.opencode.previous.$$"
  local previous_manifest="$STAGE_ROOT/previous-manifest.json"

  rm -rf "$incoming" "$rollback_path"
  if [[ -e "$OPENCODE_MANIFEST_PATH" || -L "$OPENCODE_MANIFEST_PATH" ]]; then
    # The prior manifest was captured (and, in force mode, the narrow override
    # was validated) before snapshot/mutation in run_deploy. Commit consumes the
    # captured prior manifest and never re-validates after mutation.
    cp "$PRIOR_MANIFEST" "$previous_manifest"
  else
    # A migration without a manifest can only adopt payload files whose bytes
    # already match. Unknown files and directories are never adopted or removed.
    manifest_tool adopt "$payload" "$OPENDIR" "$previous_manifest"
  fi

  # Reject payload managed files that would overwrite unowned (non-managed)
  # live files before any mutation, so unknown files always survive.
  if [[ -f "$previous_manifest" ]]; then
    manifest_tool collisions "$payload" "$previous_manifest" "$OPENDIR" ||
      fail "unowned payload collision detected; refusing deployment"
  fi

  mkdir -p "$incoming"
  # Seed the incoming tree from the pre-validated live snapshot (not a re-read
  # of the live directory) so unknown files present at snapshot time survive
  # the replacement exactly as captured. Force mode runs without a snapshot and
  # seeds directly from the live directory instead, with no rollback backup.
  if [[ "$FORCE" = true ]]; then
    if [[ -e "$OPENDIR" ]]; then
      [[ ! -L "$OPENDIR" && -d "$OPENDIR" ]] || fail "OpenCode config path changed to a non-regular directory"
      cp -R "$OPENDIR/." "$incoming/"
    fi
  elif [[ "$LIVE_WAS_PRESENT" = true && -d "$LIVE_SNAPSHOT" ]]; then
    cp -R "$LIVE_SNAPSHOT/." "$incoming/"
  elif [[ -e "$OPENDIR" ]]; then
    [[ ! -L "$OPENDIR" && -d "$OPENDIR" ]] || fail "OpenCode config path changed to a non-regular directory"
    cp -R "$OPENDIR/." "$incoming/"
  fi

  # Remove only exact paths from the previous manifest. Managed directories are
  # removed only when empty, so unknown user entries survive the replacement.
  manifest_tool remove "$incoming" "$previous_manifest"
  manifest_tool install "$payload" "$incoming"

  validate_json_file "$incoming/opencode.json"
  validate_json_file "$incoming/oh-my-opencode-slim.json"
  validate_jsonc_file "$incoming/opencode.jsonc"
  validate_jsonc_file "$incoming/rulesync.jsonc"

  if [[ "$FORCE" = true ]]; then
    replace_live_configuration_force "$incoming"
    return $?
  fi

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
  # Clear the committed marker before discarding the rollback backup so a
  # marker-removal failure leaves the rollback in place as durable recovery
  # state for the next startup's recovery pass.
  if ! remove_opencode_transaction_marker; then
    red "  ❌ OpenCode transaction marker cleanup failed; preserving marker and rollback for startup recovery"
    return 1
  fi
  if ! rm -rf "$rollback_path"; then
    red "  ❌ could not remove the committed OpenCode rollback path; preserving it for recovery"
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
    red "  ❌ could not install worktree-state helper; existing deployment rollback will restore replaced destinations"
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

run_compatibility_check() {
  echo "🔎 Read-only OpenCode/OMO compatibility preflight"
  echo ""
  # Compatibility-check is static diagnostics that gates a separate external
  # runtime smoke follow-up. It never creates or alters deployment state.
  if ! preflight_dependencies true; then
    fail "dependency preflight failed"
    return 1
  fi
  preflight_compatibility
  if [[ "$COMPATIBILITY_STATUS" != "matched" ]]; then
    yellow "  ⚠️  compatibility status is $COMPATIBILITY_STATUS; runtime smoke is blocked"
    return 1
  fi
}

run_check() {
  echo "🔍 Building temporary global deployment to check for drift..."
  echo ""
  DRIFT=0
  if [[ -e "$OPENCODE_TRANSACTION_MARKER" || -L "$OPENCODE_TRANSACTION_MARKER" ]]; then
    DRIFT=1
    red "  ⚠️  pending OpenCode deployment transaction requires recovery"
  fi
  preflight_dependencies true || DRIFT=1
  if [[ -n "${OPENCODE_BIN:-}" && -n "${PYTHON_BIN:-}" ]]; then
    preflight_compatibility
  fi
  if [[ -L "$RTK_PLUGIN_PATH" || ! -f "$RTK_PLUGIN_PATH" ]]; then
    DRIFT=1
    red "  ⚠️  RTK OpenCode plugin is missing or not a regular file: $RTK_PLUGIN_PATH"
  fi
  if [[ -z "${PYTHON_BIN:-}" ]] || ! omo_installed; then
    DRIFT=1
    red "  ⚠️  oh-my-opencode-slim package metadata is missing or invalid"
  fi
  if ! build_staged_payload; then
    red "  ⚠️  staged rulesync/OpenCode assets could not be validated"
    DRIFT=1
  else
    local payload="$STAGE_ROOT/payload"
    if [[ -e "$OPENCODE_MANIFEST_PATH" || -L "$OPENCODE_MANIFEST_PATH" ]]; then
      if ! manifest_tool compare "$payload" "$OPENDIR"; then
        DRIFT=1
      fi
    else
      DRIFT=1
      red "  ⚠️  OpenCode ownership manifest is missing: $OPENCODE_MANIFEST_PATH"
    fi
    if ! detect_reviewer_shadow "$payload/skills/reviewer/SKILL.md"; then
      DRIFT=1
    fi
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

  # Recovery validation needs Python before the broader dependency preflight;
  # resolving this executable is read-only and happens before recovery or any
  # dependency/configuration mutation.
  resolve_command PYTHON_BIN "Python 3" python3 || fail "Python 3 is required for transaction recovery"

  # Recover a transaction left by an interrupted process before any new
  # dependency or configuration mutation.
  recover_pending_opencode_transaction

  # All executable checks happen before any generated configuration mutation.
  yellow "  ⚠️  Preflight/package side effects are outside deployment rollback: GitNexus npm state, Serena uv state and global config, RTK/Homebrew state, and OMO package/cache state."
  preflight_dependencies false || fail "dependency preflight failed"
  # Host/package compatibility probing is intentionally not part of normal
  # deployment: probing unrelated package metadata on every deploy is wasteful.
  # The explicit, fail-closed gate remains `./deploy.sh --compatibility-check`.
  build_staged_payload
  # Normal deploy keeps strict ownership-manifest validation. Force mode defers
  # it to the force override preflight below, which relaxes only the content-hash
  # drift of the two mutable config files (opencode.json / opencode.jsonc); every
  # other structural, path-safety, ownership, transaction, and collision check
  # stays strict and fail-closed.
  if [[ "$FORCE" != true ]]; then
    if [[ -e "$OPENCODE_MANIFEST_PATH" || -L "$OPENCODE_MANIFEST_PATH" ]]; then
      manifest_tool validate "$OPENCODE_MANIFEST_PATH" "$OPENDIR" ||
        fail "existing OpenCode ownership manifest is invalid; refusing deployment"
    fi
  fi
  detect_reviewer_shadow "$STAGE_ROOT/payload/skills/reviewer/SKILL.md" ||
    fail "reviewer shadow configuration requires manual reconciliation"
  # Capture the prior ownership manifest before any snapshot or mutation so
  # force override validation runs against a stable, structurally-valid prior
  # state.
  if [[ -e "$OPENCODE_MANIFEST_PATH" || -L "$OPENCODE_MANIFEST_PATH" ]]; then
    capture_prior_manifest ||
      fail "could not capture prior ownership manifest"
  fi
  # Force mode validates the narrow override before the RTK plugin init, the
  # OMO package install, snapshot creation, or any live mutation. The validated
  # plan is consumed by the commit path and is never re-validated after
  # mutation. Force mode creates no snapshot or rollback backup state.
  if [[ "$FORCE" = true && -n "$PRIOR_MANIFEST" ]]; then
    manifest_override_plan "$STAGE_ROOT/payload" "$PRIOR_MANIFEST" "$OPENDIR" "$STAGE_ROOT/force-plan.json" ||
      fail "force override preflight failed; refusing deployment"
    preflight_force_summary "$STAGE_ROOT/payload" "$OPENDIR"
  fi
  if [[ "$FORCE" != true ]]; then
    snapshot_live_configuration
  fi
  initialize_rtk_plugin

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
  compatibility)
    run_compatibility_check
    ;;
  deploy)
    run_deploy
    ;;
esac
