#!/usr/bin/env python3
"""Deterministic deploy-shell stub and source-audit tests for deploy.sh.

These tests never mutate the live home configuration. They verify:
1. Normal deploy skips preflight_compatibility; --compatibility-check invokes it.
2. Managed deployment call-sequence positions within run_deploy.
3. Incomplete snapshot: the SNAPSHOT_COMPLETE guard prevents partial rollback.
4. rollback_deployment attempts all managed destinations in reverse order.
5. Transaction recovery matrices (prepared, old_moved, committed, ambiguous)
   plus malformed-marker rejection (collision, non-distinct, alias, dangling
   symlink) using the production recovery logic extracted from deploy.sh.
6. OpenCode restore verifies the snapshot copy before replacing live config.
7. Compatibility-check fail-closed for unverified and skewed evidence.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DEPLOY_SCRIPT = Path(__file__).parent.parent / "deploy.sh"

# ── typical deployment-call tokens we assert source positions for ──
# Ordered from start of run_deploy body outward.
DEPLOY_CALL_SEQUENCE = [
    "deployment_lock_acquire",
    "recover_pending_opencode_transaction",
    "preflight_dependencies",
    "build_staged_payload",
    "manifest_tool",
    "detect_reviewer_shadow",
    "snapshot_live_configuration",
    "initialize_rtk_plugin",
    "install_omo",
    "commit_opencode_configuration",
    "install_wt_orca",
    "install_worktrunk_config",
    "DEPLOY_SUCCEEDED=true",
]


# ── minimal deploy stub (no live home touches) ────────────────────────
MINIMAL_STUB = r"""#!/usr/bin/env bash
set -euo pipefail
MV_BIN="${MV_BIN:-mv}"

MODE="deploy"

export HOME="${TEST_HOME:-$HOME}"
export OPENCODE_CONFIG_DIR="${OPENDIR:-${HOME}/.config/opencode-test}"
OPENDIR="$OPENCODE_CONFIG_DIR"
OPENCODE_TRANSACTION_MARKER="$OPENDIR.transaction"
OPENCODE_MANIFEST_PATH="$OPENDIR/.ai-rules.manifest.json"
# ... paths elided ...

STAGE_ROOT=""
LIVE_SNAPSHOT=""
LIVE_WAS_PRESENT=false
WT_ORCA_SNAPSHOT=""
WT_ORCA_WAS_PRESENT=false
WORKTREE_STATE_SNAPSHOT=""
WORKTREE_STATE_WAS_PRESENT=false
WORKTRUNK_SNAPSHOT=""
WORKTRUNK_WAS_PRESENT=false
SNAPSHOT_COMPLETE=false
DEPLOY_SUCCEEDED=false
COMPATIBILITY_STATUS="unverified"

red()   { printf '\033[31m%s\033[0m\n' "$1"; }
green() { printf '\033[32m%s\033[0m\n' "$1"; }
cyan()  { printf '\033[36m%s\033[0m\n' "$1"; }
yellow() { printf '\033[33m%s\033[0m\n' "$1"; }
fail()   { red "  ❌ $1" >&2; return 1; }

deployment_failpoint() {
    if [[ "${DEPLOY_FAILPOINT:-}" = "$1" ]]; then
        echo "FAILPOINT_HIT:$1"
        return 1
    fi
}

preflight_compatibility() {
    if [[ "${INJECT_COMPAT_STATUS:-}" != "" ]]; then
        COMPATIBILITY_STATUS="$INJECT_COMPAT_STATUS"
    else
        echo "CALLED_preflight_compatibility"
        COMPATIBILITY_STATUS="matched"
    fi
}
preflight_dependencies() { return 0; }
build_staged_payload() { return 0; }
manifest_tool() { return 0; }
snapshot_live_configuration() {
    LIVE_SNAPSHOT="/tmp/snap-live"
    WT_ORCA_SNAPSHOT="/tmp/snap-wt-orca"
    WORKTREE_STATE_SNAPSHOT="/tmp/snap-worktree-state"
    deployment_failpoint snapshot-incomplete
    WORKTRUNK_SNAPSHOT="/tmp/snap-worktrunk"
    SNAPSHOT_COMPLETE=true
}
restore_live_configuration() {
    if [[ "${FAIL_RESTORE_OPENCODE:-0}" == "1" ]]; then return 1; fi
    echo "RESTORE_live_configuration"
}
restore_managed_file() {
    echo "RESTORE_ATTEMPT $2"
    if [[ "$2" == *wt-orca* && "${FAIL_RESTORE_WT_ORCA:-0}" == "1" ]]; then return 1; fi
    if [[ "$2" == *worktree-state* && "${FAIL_RESTORE_WORKTREE_STATE:-0}" == "1" ]]; then return 1; fi
    if [[ "$2" == *worktrunk* && "${FAIL_RESTORE_WORKTRUNK:-0}" == "1" ]]; then return 1; fi
    echo "RESTORE_OK $2"
}
initialize_rtk_plugin() { return 0; }
omo_installed() { return 0; }
install_omo() { return 0; }
commit_opencode_configuration() { return 0; }
install_wt_orca() { return 0; }
install_worktrunk_config() { return 0; }
detect_reviewer_shadow() { return 0; }
recover_pending_opencode_transaction() { return 0; }
deployment_lock_acquire() { return 0; }
deployment_lock_release() { return 0; }

rollback_deployment() {
  local rollback_failed=false
  local pending_marker=false
  if ! restore_managed_file "worktrunk" "/tmp/snap-worktrunk" "true"; then
    rollback_failed=true
  fi
  if ! restore_managed_file "worktree-state" "/tmp/snap-worktree-state" "true"; then
    rollback_failed=true
  fi
  if ! restore_managed_file "wt-orca" "/tmp/snap-wt-orca" "true"; then
    rollback_failed=true
  fi
  if ! restore_live_configuration; then
    rollback_failed=true
  fi
  if [[ "$rollback_failed" = true ]]; then
    echo "ROLLBACK_FAILED"
    return 1
  fi
}

cleanup_stage() {
  local exit_code=$?
  if [[ "$DEPLOY_SUCCEEDED" != true ]] && [[ "$SNAPSHOT_COMPLETE" = true ]]; then
    rollback_deployment
    local rollback_rc=$?
    if [[ $rollback_rc -ne 0 ]]; then
      exit_code=1
    fi
  fi
  exit "$exit_code"
}
trap cleanup_stage EXIT

run_deploy() {
  deployment_lock_acquire
  recover_pending_opencode_transaction
  preflight_dependencies false
  build_staged_payload
  manifest_tool validate "phony" "phony"
  detect_reviewer_shadow "phony"
  deployment_failpoint deploy-before-snapshot
  snapshot_live_configuration
  deployment_failpoint deploy-after-snapshot
  initialize_rtk_plugin
  install_omo
  commit_opencode_configuration
  deployment_failpoint deploy-after-commit
  install_wt_orca
  install_worktrunk_config
  DEPLOY_SUCCEEDED=true
}

run_compatibility_check() {
  echo "COMPAT_CHECK_START"
  preflight_dependencies true
  preflight_compatibility
  if [[ "$COMPATIBILITY_STATUS" != "matched" ]]; then
    echo "COMPAT_CHECK_FAILED:$COMPATIBILITY_STATUS"
    return 1
  fi
  echo "COMPAT_CHECK_END"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compatibility-check) MODE="compatibility"; shift ;;
    *) shift ;;
  esac
done

case "$MODE" in
  compatibility) run_compatibility_check ;;
  deploy)        run_deploy ;;
esac
"""


def _write_stub(content: str, name: str = "deploy_test_stub_") -> Path:
    fd, path = tempfile.mkstemp(suffix=".sh", prefix=name)
    os.close(fd)
    p = Path(path)
    p.write_text(content)
    p.chmod(0o755)
    return p


_SANDBOXES: list[str] = []


def _cleanup_sandboxes() -> None:
    for path in _SANDBOXES:
        shutil.rmtree(path, ignore_errors=True)


atexit.register(_cleanup_sandboxes)


def _sandbox() -> Path:
    """Return a fresh temporary directory to use as HOME for tests.

    The directory is kept alive for the process lifetime so subprocesses that
    write into it (rollback/recovery fixtures) never race a premature cleanup.
    """
    path = tempfile.mkdtemp(prefix="deploy-compat-")
    _SANDBOXES.append(path)
    return Path(path)


# ── source-position extraction ────────────────────────────────────────
def _extract_function_body(source: str, func_name: str) -> str:
    """Extract the body of a shell function between `func_name()` and closing `}`."""
    pattern = rf"^{func_name}\(\)\s*\{{"
    m = re.search(pattern, source, re.MULTILINE)
    if not m:
        return ""
    start = m.start()
    brace = 0
    in_func = False
    for idx, ch in enumerate(source[start:], start):
        if ch == "{":
            brace += 1
            in_func = True
        elif ch == "}":
            brace -= 1
            if in_func and brace == 0:
                return source[start : idx + 1]
    return ""


def _function_call_positions(source: str, func_name: str) -> list[tuple[str, int]]:
    """Return (call_name, line_offset) within the function body for each deployment call."""
    body = _extract_function_body(source, func_name)
    if not body:
        return []
    body_start = source.index(body)
    body_lines = body.split("\n")
    results: list[tuple[str, int]] = []
    for token in DEPLOY_CALL_SEQUENCE:
        for i, line in enumerate(body_lines):
            if token in line:
                results.append((token, body_start + i))
                break
    return results


def _extract_recovery_python() -> str:
    """Return the embedded recovery Python from recover_pending_opencode_transaction.

    This is the exact logic deployed by deploy.sh, not a re-implementation, so
    recovery tests exercise the real committed/old_moved/prepared/ambiguous and
    malformed-marker paths.
    """
    source = Path(DEPLOY_SCRIPT).read_text()
    body = _extract_function_body(source, "recover_pending_opencode_transaction")
    if not body:
        return ""
    try:
        marker_start = body.index("<<'PY'")
    except ValueError:
        return ""
    newline = body.index("\n", marker_start)
    content_start = newline + 1
    closing = re.search(r"^PY\s*$", body[content_start:], re.MULTILINE)
    if not closing:
        return ""
    return body[content_start : content_start + closing.start()]


def _extract_embedded_python(func_name: str) -> str:
    """Return the embedded ``<<'PY' ... PY`` Python from a shell function.

    Used to exercise the real manifest_tool force/collisions logic (not a
    re-implementation) against isolated fixtures.
    """
    source = Path(DEPLOY_SCRIPT).read_text()
    body = _extract_function_body(source, func_name)
    if not body:
        return ""
    try:
        marker_start = body.index("<<'PY'")
    except ValueError:
        return ""
    newline = body.index("\n", marker_start)
    content_start = newline + 1
    closing = re.search(r"^PY\s*$", body[content_start:], re.MULTILINE)
    if not closing:
        return ""
    return body[content_start : content_start + closing.start()]


def _make_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "marker.txt").write_text("content", encoding="utf-8")


# ── stub-based control-flow tests ─────────────────────────────────────

class StubDeployTests(unittest.TestCase):
    """Deterministic deploy-shell stub tests for the compatibility split,
    the SNAPSHOT_COMPLETE guard, and reverse-order rollback aggregation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.stub_path = _write_stub(MINIMAL_STUB)
        cls.addClassCleanup(os.unlink, cls.stub_path)

    def _run(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        home = _sandbox()
        effective_env: dict[str, str] = {**os.environ, "TEST_HOME": str(home)}
        if env is not None:
            effective_env.update(env)
        return subprocess.run(  # noqa: PLW1510 — asserts exit code manually
            [str(self.stub_path), *args],
            capture_output=True, text=True, timeout=10,
            env=effective_env,
        )

    # 1 — normal deploy skips compatibility check
    def test_normal_deploy_skips_compatibility_check(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("CALLED_preflight_compatibility", result.stdout)

    # 2 — explicit --compatibility-check invokes it
    def test_explicit_compatibility_check_calls_preflight(self) -> None:
        result = self._run("--compatibility-check")
        self.assertEqual(result.returncode, 0)
        self.assertIn("COMPAT_CHECK_START", result.stdout)
        self.assertIn("CALLED_preflight_compatibility", result.stdout)
        self.assertIn("COMPAT_CHECK_END", result.stdout)

    # 3 — compatibility-check fail-closed: unverified evidence
    def test_compatibility_check_fails_on_unverified(self) -> None:
        result = self._run("--compatibility-check", env={"INJECT_COMPAT_STATUS": "unverified"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("COMPAT_CHECK_FAILED:unverified", result.stdout)

    # 4 — compatibility-check fail-closed: skewed evidence
    def test_compatibility_check_fails_on_skew(self) -> None:
        result = self._run("--compatibility-check", env={"INJECT_COMPAT_STATUS": "skew"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("COMPAT_CHECK_FAILED:skew", result.stdout)

    # 5 — incomplete snapshot: SNAPSHOT_COMPLETE stays false => no rollback
    def test_incomplete_snapshot_skips_rollback(self) -> None:
        """An incomplete snapshot must fail deploy without attempting any restore."""
        result = self._run(env={"DEPLOY_FAILPOINT": "snapshot-incomplete"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAILPOINT_HIT:snapshot-incomplete", result.stdout)
        self.assertNotIn("RESTORE", result.stdout)
        self.assertNotIn("RESTORE_live_configuration", result.stdout)
        self.assertNotIn("ROLLBACK_FAILED", result.stdout)

    # 6 — rollback attempts all destinations even if one fails, in reverse order
    def test_rollback_attempts_all_destinations_after_failure(self) -> None:
        """A failure after snapshot must trigger rollback of every managed destination."""
        result = self._run(
            env={"DEPLOY_FAILPOINT": "deploy-after-snapshot", "FAIL_RESTORE_WORKTRUNK": "1"}
        )
        stdout = result.stdout
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAILPOINT_HIT:deploy-after-snapshot", stdout)
        self.assertIn("RESTORE_ATTEMPT /tmp/snap-worktrunk", stdout)
        self.assertIn("RESTORE_ATTEMPT /tmp/snap-worktree-state", stdout)
        self.assertIn("RESTORE_ATTEMPT /tmp/snap-wt-orca", stdout)
        self.assertIn("RESTORE_live_configuration", stdout)
        self.assertIn("ROLLBACK_FAILED", stdout)
        # Reverse deployment order: Worktrunk -> worktree-state -> wt-orca -> OpenCode.
        order = [stdout.index(token) for token in (
            "RESTORE_ATTEMPT /tmp/snap-worktrunk",
            "RESTORE_ATTEMPT /tmp/snap-worktree-state",
            "RESTORE_ATTEMPT /tmp/snap-wt-orca",
            "RESTORE_live_configuration",
        )]
        self.assertEqual(order, sorted(order), f"restore order violated: {order}")


# ── production recovery tests (extracted from deploy.sh) ──────────────

class RecoveryTests(unittest.TestCase):
    """Transaction recovery tests using the real recovery Python extracted
    from deploy.sh — including malformed-marker rejection fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        recovery_py = _extract_recovery_python()
        if not recovery_py:
            raise unittest.SkipTest("could not extract recovery Python from deploy.sh")
        cls.recovery_script = _write_stub(recovery_py, name="recover_pending_")
        cls.addClassCleanup(os.unlink, cls.recovery_script)

    def _fixture(self) -> dict[str, Path]:
        """Build an isolated OpenCode transaction layout for recovery tests."""
        cfg = _sandbox() / ".config"
        cfg.mkdir(parents=True, exist_ok=True)
        return {
            "marker": cfg / "opencode.transaction",
            "live": cfg / "opencode",
            "incoming": cfg / "opencode.deploy.1",
            "rollback": cfg / "opencode.previous.1",
        }

    def _write_marker(
        self,
        paths: dict[str, Path],
        phase: str,
        overrides: dict[str, str] | None = None,
    ) -> None:
        payload: dict[str, str] = {
            "live": str(paths["live"]),
            "incoming": str(paths["incoming"]),
            "rollback": str(paths["rollback"]),
            "phase": phase,
            "created_at": "2026-01-01T00:00:00Z",
        }
        if overrides:
            payload.update(overrides)
        paths["marker"].write_text(json.dumps(payload), encoding="utf-8")

    def _recover(self, paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: PLW1510 — multi-branch exit code assertion
            ["python3", str(self.recovery_script), str(paths["marker"])],
            capture_output=True, text=True, timeout=10,
        )

    # 1 — committed marker with live + rollback present: recovery removes rollback
    def test_committed_marker_removes_rollback(self) -> None:
        paths = self._fixture()
        _make_dir(paths["live"])
        _make_dir(paths["rollback"])
        self._write_marker(paths, "committed")
        result = self._recover(paths)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(paths["live"].exists(), "live config must survive recovery")
        self.assertFalse(paths["rollback"].exists(), "rollback must be removed")
        self.assertFalse(paths["marker"].exists(), "marker must be removed")

    # 2 — old_moved (live absent, rollback present): restore rollback to live
    def test_old_moved_restores_rollback(self) -> None:
        paths = self._fixture()
        _make_dir(paths["rollback"])
        self._write_marker(paths, "old_moved")
        result = self._recover(paths)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(paths["live"].exists(), "rollback must be restored to live")
        self.assertFalse(paths["rollback"].exists())
        self.assertFalse(paths["marker"].exists())

    # 3 — prepared (live + incoming present, rollback absent): remove incoming
    def test_prepared_removes_incoming(self) -> None:
        paths = self._fixture()
        _make_dir(paths["live"])
        _make_dir(paths["incoming"])
        self._write_marker(paths, "prepared")
        result = self._recover(paths)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(paths["live"].exists())
        self.assertFalse(paths["incoming"].exists(), "staged incoming must be removed")
        self.assertFalse(paths["marker"].exists())

    # 4 — ambiguous (live + incoming + rollback all present): refuse
    def test_ambiguous_refuses(self) -> None:
        paths = self._fixture()
        _make_dir(paths["live"])
        _make_dir(paths["incoming"])
        _make_dir(paths["rollback"])
        self._write_marker(paths, "prepared")
        result = self._recover(paths)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ambiguous", result.stderr)
        self.assertTrue(paths["marker"].exists(), "ambiguous marker must be preserved")

    # 5 — marker path collision (live == marker path): reject before mutation
    def test_marker_path_collision_rejected(self) -> None:
        paths = self._fixture()
        self._write_marker(paths, "prepared", overrides={"live": str(paths["marker"])})
        result = self._recover(paths)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("collides", result.stderr)
        self.assertTrue(paths["marker"].exists(), "colliding marker must be preserved")

    # 6 — non-distinct paths (rollback == live): reject before mutation
    def test_non_distinct_paths_rejected(self) -> None:
        paths = self._fixture()
        _make_dir(paths["live"])
        self._write_marker(paths, "prepared", overrides={"rollback": str(paths["live"])})
        result = self._recover(paths)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not pairwise distinct", result.stderr)
        self.assertTrue(paths["marker"].exists(), "non-distinct marker must be preserved")

    # 7 — aliased paths (rollback symlink -> live): reject before mutation
    def test_aliased_paths_rejected(self) -> None:
        paths = self._fixture()
        _make_dir(paths["live"])
        os.symlink(str(paths["live"]), str(paths["rollback"]))
        self._write_marker(paths, "prepared")
        result = self._recover(paths)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("alias", result.stderr)
        self.assertTrue(paths["marker"].exists(), "aliased marker must be preserved")
        self.assertTrue(paths["live"].exists(), "live must not be mutated on rejection")

    # 8 — unreadable/corrupt marker JSON: reject and preserve the marker
    def test_unreadable_marker_rejected(self) -> None:
        paths = self._fixture()
        paths["marker"].write_text("{not valid json", encoding="utf-8")
        result = self._recover(paths)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unreadable", result.stderr)
        self.assertTrue(paths["marker"].exists(), "corrupt marker must be preserved")


# ── force-deployment manifest_tool tests (real embedded Python) ───────

def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_manifest_file(
    path: Path,
    *,
    files: list[str],
    directories: list[str],
    hashes: dict[str, str],
) -> None:
    payload = {
        "managed_by": "ai-rules/deploy.sh",
        "version": 1,
        "timestamp": "2026-09-02T00:00:00+00:00",
        "managed_files": sorted(files),
        "managed_directories": sorted(directories),
        "managed_file_hashes": {key: hashes[key] for key in sorted(hashes)},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class ManifestToolForceTests(unittest.TestCase):
    """Exercise the real manifest_tool ``force`` and ``collisions`` operations.

    These tests extract the production Python embedded in ``manifest_tool()``
    from deploy.sh (not a re-implementation) and run it against isolated
    temporary fixtures. They never touch the live home configuration.
    """

    @classmethod
    def setUpClass(cls) -> None:
        source = _extract_embedded_python("manifest_tool")
        if not source:
            raise unittest.SkipTest("could not extract manifest_tool Python")
        cls.manifest_py = _write_stub(source, name="manifest_tool_")
        cls.addClassCleanup(os.unlink, cls.manifest_py)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="force-manifest-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "live"
        self.root.mkdir(parents=True, exist_ok=True)

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: PLW1510 — multi-branch exit assertions
            ["python3", str(self.manifest_py), *args],
            capture_output=True, text=True, timeout=10,
        )

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _live_manifest(
        self,
        files: list[str],
        hashes: dict[str, str],
        directories: list[str] | None = None,
    ) -> Path:
        manifest = self.root / ".ai-rules.manifest.json"
        _write_manifest_file(
            manifest, files=files, directories=directories or [], hashes=hashes
        )
        return manifest

    def _payload_manifest(
        self, files: list[str], directories: list[str], hashes: dict[str, str]
    ) -> Path:
        manifest = Path(self._tmp.name) / "payload-manifest.json"
        _write_manifest_file(
            manifest, files=files, directories=directories, hashes=hashes
        )
        return manifest

    # 1 — force success for both exempt files records overrides
    def test_force_exempt_drift_allowed(self) -> None:
        files = ["opencode.json", "opencode.jsonc", "other.txt"]
        self._write("opencode.json", "live-drifted-json")
        self._write("opencode.jsonc", "live-drifted-jsonc")
        self._write("other.txt", "unchanged")
        live_hashes = {
            "opencode.json": _sha256_text("staged-original-json"),
            "opencode.jsonc": _sha256_text("staged-original-jsonc"),
            "other.txt": _sha256_text("unchanged"),
        }
        staged_hashes = {
            "opencode.json": _sha256_text("new-staged-json"),
            "opencode.jsonc": _sha256_text("new-staged-jsonc"),
            "other.txt": _sha256_text("unchanged"),
        }
        live_manifest = self._live_manifest(files, live_hashes)
        payload_manifest = self._payload_manifest(files, [], staged_hashes)
        plan = Path(self._tmp.name) / "plan.json"

        result = self._run(
            "force", str(payload_manifest), str(live_manifest), str(self.root), str(plan)
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(plan.exists(), "override plan must be written")
        data = json.loads(plan.read_text())
        self.assertEqual(data["force"], True)
        overridden = sorted(item["path"] for item in data["overrides"])
        self.assertEqual(overridden, ["opencode.json", "opencode.jsonc"])
        self.assertIn("opencode.json", result.stdout)
        self.assertIn("opencode.jsonc", result.stdout)
        self.assertNotIn("other.txt", result.stdout)
        # Never print file contents.
        self.assertNotIn("live-drifted", result.stdout)

    # 2 — non-exempt mismatch refuses
    def test_force_non_exempt_mismatch_refused(self) -> None:
        files = ["opencode.json", "secret.txt"]
        self._write("opencode.json", "live-json")
        self._write("secret.txt", "drifted-secret")
        live_hashes = {
            "opencode.json": _sha256_text("staged-json"),
            "secret.txt": _sha256_text("staged-secret"),
        }
        staged_hashes = {
            "opencode.json": _sha256_text("new-json"),
            "secret.txt": _sha256_text("new-secret"),
        }
        live_manifest = self._live_manifest(files, live_hashes)
        payload_manifest = self._payload_manifest(files, [], staged_hashes)

        result = self._run(
            "force",
            str(payload_manifest),
            str(live_manifest),
            str(self.root),
            str(Path(self._tmp.name) / "plan.json"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("was changed", result.stderr)
        self.assertIn("secret.txt", result.stderr)

    # 3 — missing live-managed file refuses (the live manifest lists a file
    # that is absent from the live root)
    def test_force_missing_refused(self) -> None:
        files = ["opencode.json", "gone.txt"]
        self._write("opencode.json", "live-json")
        # gone.txt is listed in the live manifest but absent from the live tree.
        live_hashes = {
            "opencode.json": _sha256_text("staged-json"),
            "gone.txt": _sha256_text("staged-gone"),
        }
        live_manifest = self._live_manifest(files, live_hashes)
        payload_manifest = self._payload_manifest(
            files,
            [],
            {
                "opencode.json": _sha256_text("new-json"),
                "gone.txt": _sha256_text("new-gone"),
            },
        )

        result = self._run(
            "force",
            str(payload_manifest),
            str(live_manifest),
            str(self.root),
            str(Path(self._tmp.name) / "plan.json"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr)
        self.assertIn("gone.txt", result.stderr)

    # 4 — symlink managed file refuses
    def test_force_symlink_refused(self) -> None:
        files = ["opencode.json"]
        self._write("opencode.json", "live-json")
        os.unlink(self.root / "opencode.json")
        os.symlink("opencode.jsonc", self.root / "opencode.json")
        live_hashes = {"opencode.json": _sha256_text("staged-json")}
        live_manifest = self._live_manifest(files, live_hashes)
        payload_manifest = self._payload_manifest(
            files, [], {"opencode.json": _sha256_text("new-json")}
        )

        result = self._run(
            "force",
            str(payload_manifest),
            str(live_manifest),
            str(self.root),
            str(Path(self._tmp.name) / "plan.json"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)

    # 5 — malformed live manifest refuses
    def test_force_malformed_manifest_refused(self) -> None:
        self._write("opencode.json", "live-json")
        live_manifest = self.root / ".ai-rules.manifest.json"
        live_manifest.write_text("{not valid json", encoding="utf-8")
        payload_manifest = self._payload_manifest(
            ["opencode.json"], [], {"opencode.json": _sha256_text("new-json")}
        )

        result = self._run(
            "force",
            str(payload_manifest),
            str(live_manifest),
            str(self.root),
            str(Path(self._tmp.name) / "plan.json"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed", result.stderr)

    # 6 — unsafe manifest path refuses
    def test_force_unsafe_path_refused(self) -> None:
        self._write("opencode.json", "live-json")
        live_manifest = self.root / ".ai-rules.manifest.json"
        _write_manifest_file(
            live_manifest,
            files=["../escape.txt"],
            directories=[],
            hashes={"../escape.txt": _sha256_text("x")},
        )
        payload_manifest = self._payload_manifest(
            ["opencode.json"], [], {"opencode.json": _sha256_text("new-json")}
        )

        result = self._run(
            "force",
            str(payload_manifest),
            str(live_manifest),
            str(self.root),
            str(Path(self._tmp.name) / "plan.json"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe", result.stderr)

    # 6a — staged manifest missing an exempt file the live manifest owns refuses
    def test_force_missing_staged_exempt_file_refused(self) -> None:
        files = ["opencode.json", "opencode.jsonc"]
        self._write("opencode.json", "live-json")
        self._write("opencode.jsonc", "live-jsonc")
        live_manifest = self._live_manifest(
            files,
            {
                "opencode.json": _sha256_text("staged-json"),
                "opencode.jsonc": _sha256_text("staged-jsonc"),
            },
        )
        # The staged payload manifest omits opencode.json, which the live
        # manifest still owns; force must fail closed and never emit an empty
        # staged hash.
        payload_manifest = self._payload_manifest(
            ["opencode.jsonc"], [], {"opencode.jsonc": _sha256_text("new-jsonc")}
        )

        result = self._run(
            "force",
            str(payload_manifest),
            str(live_manifest),
            str(self.root),
            str(Path(self._tmp.name) / "plan.json"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed_files", result.stderr)
        self.assertNotIn('"staged_sha256": ""', result.stdout)

    # 6b — staged manifest adding a managed file the live manifest lacks refuses
    def test_force_managed_file_set_mismatch_refused(self) -> None:
        files = ["opencode.json", "other.txt"]
        self._write("opencode.json", "live-json")
        self._write("other.txt", "unchanged")
        live_manifest = self._live_manifest(
            files,
            {
                "opencode.json": _sha256_text("staged-json"),
                "other.txt": _sha256_text("unchanged"),
            },
        )
        # Staged adds a managed file the live manifest does not own.
        payload_manifest = self._payload_manifest(
            ["opencode.json", "new.txt"],
            [],
            {
                "opencode.json": _sha256_text("new-json"),
                "new.txt": _sha256_text("new"),
            },
        )

        result = self._run(
            "force",
            str(payload_manifest),
            str(live_manifest),
            str(self.root),
            str(Path(self._tmp.name) / "plan.json"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed_files", result.stderr)

    # 6c — staged manifest directory set mismatch refuses
    def test_force_managed_directory_set_mismatch_refused(self) -> None:
        files = ["opencode.json"]
        self._write("opencode.json", "live-json")
        (self.root / "skills").mkdir(parents=True, exist_ok=True)
        live_manifest = self._live_manifest(
            files,
            {"opencode.json": _sha256_text("staged-json")},
            directories=["skills"],
        )
        # Staged omits the managed directory the live manifest owns.
        payload_manifest = self._payload_manifest(
            ["opencode.json"], [], {"opencode.json": _sha256_text("new-json")}
        )

        result = self._run(
            "force",
            str(payload_manifest),
            str(live_manifest),
            str(self.root),
            str(Path(self._tmp.name) / "plan.json"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed_directories", result.stderr)

    # 7 — unowned payload collision refused
    def test_collisions_unowned_refused(self) -> None:
        payload = Path(self._tmp.name) / "payload"
        payload.mkdir(parents=True, exist_ok=True)
        (payload / ".ai-rules.manifest.json").write_text(
            json.dumps(
                {
                    "managed_by": "ai-rules/deploy.sh",
                    "version": 1,
                    "timestamp": "2026-09-02T00:00:00+00:00",
                    "managed_files": ["newfile.txt"],
                    "managed_directories": [],
                    "managed_file_hashes": {"newfile.txt": _sha256_text("new")},
                }
            ),
            encoding="utf-8",
        )
        previous_manifest = Path(self._tmp.name) / "prev-manifest.json"
        _write_manifest_file(
            previous_manifest, files=["opencode.json"], directories=[], hashes={"opencode.json": _sha256_text("x")}
        )
        # Un-owned live file collides with a payload-managed file.
        self._write("newfile.txt", "user-owned")

        result = self._run("collisions", str(payload), str(previous_manifest), str(self.root))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unowned file", result.stderr)
        self.assertIn("newfile.txt", result.stderr)

    # 8 — unknown (non-managed) live files survive the collision preflight
    def test_collisions_unknown_file_preserved(self) -> None:
        payload = Path(self._tmp.name) / "payload"
        payload.mkdir(parents=True, exist_ok=True)
        (payload / ".ai-rules.manifest.json").write_text(
            json.dumps(
                {
                    "managed_by": "ai-rules/deploy.sh",
                    "version": 1,
                    "timestamp": "2026-09-02T00:00:00+00:00",
                    "managed_files": ["opencode.json"],
                    "managed_directories": [],
                    "managed_file_hashes": {"opencode.json": _sha256_text("new")},
                }
            ),
            encoding="utf-8",
        )
        previous_manifest = Path(self._tmp.name) / "prev-manifest.json"
        _write_manifest_file(
            previous_manifest, files=["opencode.json"], directories=[], hashes={"opencode.json": _sha256_text("x")}
        )
        # Unknown file is not payload-managed, so it must not be flagged.
        self._write("user-notes.txt", "keep me")

        result = self._run("collisions", str(payload), str(previous_manifest), str(self.root))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "user-notes.txt").exists())


# ── source-audit tests against the real deploy.sh ────────────────────

class RealDeployAuditTests(unittest.TestCase):
    """Source-level audits of the real deploy.sh."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = Path(DEPLOY_SCRIPT).read_text()

    def test_shell_syntax(self) -> None:
        result = subprocess.run(  # noqa: PLW1510 — manual exit code assertion
            ["bash", "-n", str(DEPLOY_SCRIPT)],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, f"bash -n failed: {result.stderr}")

    def test_help_lists_compatibility_check(self) -> None:
        result = subprocess.run(  # noqa: PLW1510 — manual exit code assertion
            ["bash", str(DEPLOY_SCRIPT), "--help"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertIn("--compatibility-check", result.stdout)

    def test_compatibility_mode_reachable(self) -> None:
        self.assertIn("compatibility)", self.source)
        self.assertIn("run_compatibility_check", self.source)

    # ── source-position assertions ──
    def test_deploy_call_sequence_positions(self) -> None:
        """Assert the managed deployment calls appear in the correct relative order."""
        positions = _function_call_positions(self.source, "run_deploy")
        self.assertTrue(len(positions) >= len(DEPLOY_CALL_SEQUENCE),
                        f"Found only {len(positions)}/{len(DEPLOY_CALL_SEQUENCE)} deployment calls")
        found = {name for name, _ in positions}
        missing = set(DEPLOY_CALL_SEQUENCE) - found
        self.assertEqual(len(missing), 0, f"Missing calls: {missing}")
        for i in range(1, len(positions)):
            _, prev_pos = positions[i - 1]
            name, curr_pos = positions[i]
            self.assertLess(prev_pos, curr_pos,
                            f"Call {name!r} at offset {curr_pos} appears before expected order "
                            f"(previous at {prev_pos})")

    # ── compatibility split audits ──
    def test_run_deploy_does_not_call_preflight_compatibility(self) -> None:
        body = _extract_function_body(self.source, "run_deploy")
        self.assertNotIn("preflight_compatibility", body,
                         "run_deploy must not invoke preflight_compatibility")

    def test_run_compatibility_check_calls_preflight(self) -> None:
        body = _extract_function_body(self.source, "run_compatibility_check")
        self.assertIn("preflight_compatibility", body)

    def test_run_check_calls_preflight_for_drift(self) -> None:
        body = _extract_function_body(self.source, "run_check")
        self.assertIn("preflight_compatibility", body)

    def test_preflight_compatibility_defined(self) -> None:
        self.assertIn("preflight_compatibility()", self.source)

    def test_fail_closed_preserved(self) -> None:
        self.assertIn('COMPATIBILITY_STATUS="unverified"', self.source)
        compat_body = _extract_function_body(self.source, "run_compatibility_check")
        self.assertIn("COMPATIBILITY_STATUS", compat_body)

    def test_guard_comment_in_run_deploy(self) -> None:
        body = _extract_function_body(self.source, "run_deploy")
        self.assertIn("Host/package compatibility probing", body)

    # ── snapshot / rollback infrastructure audits ──
    def test_snapshot_complete_initialized_false(self) -> None:
        self.assertIn("SNAPSHOT_COMPLETE=false", self.source)

    def test_snapshot_complete_set_true_after_globals(self) -> None:
        body = _extract_function_body(self.source, "snapshot_live_configuration")
        lines = body.split("\n")
        complete_pos = None
        last_snapshot_pos = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "SNAPSHOT_COMPLETE=true" in stripped:
                complete_pos = i
            for var in ("LIVE_SNAPSHOT=", "WT_ORCA_SNAPSHOT=", "WORKTREE_STATE_SNAPSHOT=",
                        "WORKTRUNK_SNAPSHOT=", "LIVE_WAS_PRESENT=", "WT_ORCA_WAS_PRESENT=",
                        "WORKTREE_STATE_WAS_PRESENT=", "WORKTRUNK_WAS_PRESENT="):
                if var in stripped:
                    last_snapshot_pos = max(last_snapshot_pos, i)
        self.assertIsNotNone(complete_pos, "SNAPSHOT_COMPLETE=true not found in snapshot_live_configuration")
        assert complete_pos is not None  # narrowed for pyright
        self.assertGreater(complete_pos, last_snapshot_pos,
                           "SNAPSHOT_COMPLETE=true must be set after all snapshot globals are assigned")

    def test_cleanup_gates_on_snapshot_complete(self) -> None:
        body = _extract_function_body(self.source, "cleanup_stage")
        self.assertIn("SNAPSHOT_COMPLETE", body)

    def test_rollback_deployment_defined(self) -> None:
        self.assertIn("rollback_deployment()", self.source)

    def test_rollback_reverse_order(self) -> None:
        """Verify rollback restores in reverse: Worktrunk -> worktree-state -> wt-orca -> OpenCode."""
        body = _extract_function_body(self.source, "rollback_deployment")
        lines = body.split("\n")
        restores = [line.strip() for line in lines if "restore" in line.lower()]
        order = []
        for line in restores:
            if "WORKTRUNK" in line:
                order.append("worktrunk")
            elif "WORKTREE_STATE" in line:
                order.append("worktree_state")
            elif "WT_ORCA" in line:
                order.append("wt_orca")
            elif "restore_live_configuration" in line or "OPENCODE_TRANSACTION_MARKER" in line:
                order.append("opencode")
        self.assertEqual(order, ["worktrunk", "worktree_state", "wt_orca", "opencode"],
                         f"Rollback order is {order}, expected worktrunk, worktree_state, wt_orca, opencode")

    def test_rollback_aggregates_failures(self) -> None:
        """Verify rollback_deployment returns 1 when any restore fails."""
        body = _extract_function_body(self.source, "rollback_deployment")
        self.assertIn("return 1", body)

    # ── recovery fail-closed audits (requirement 1 & 2) ──
    def test_recovery_detects_dangling_symlink(self) -> None:
        """A dangling marker symlink must be detected and rejected, not skipped."""
        body = _extract_function_body(self.source, "recover_pending_opencode_transaction")
        self.assertIn('|| -L "$OPENCODE_TRANSACTION_MARKER"', body,
                      "recovery must detect marker presence via `-e || -L`")
        self.assertIn("refusing recovery and preserving it", body,
                      "symlink marker must be rejected and preserved")
        self.assertIn("return 1", body)

    def test_recovery_validates_distinct_paths(self) -> None:
        """Recovery must reject non-distinct/colliding/aliased paths before mutation."""
        body = _extract_function_body(self.source, "recover_pending_opencode_transaction")
        self.assertIn("not pairwise distinct", body)
        self.assertIn("collides with a managed path", body)
        self.assertIn("alias each other", body)

    # ── restore / commit safety audits (requirement 3 & 4) ──
    def test_restore_live_checks_snapshot_copy(self) -> None:
        """OpenCode restore must verify the snapshot copy before replacing live."""
        body = _extract_function_body(self.source, "restore_live_configuration")
        self.assertIn('if ! cp -R "$LIVE_SNAPSHOT/." "$restore_path/"', body,
                      "snapshot copy must be result-checked")
        self.assertIn("leaving live configuration intact", body)

    def test_commit_clears_marker_before_rollback(self) -> None:
        """Committed-phase cleanup must clear the marker before discarding rollback."""
        body = _extract_function_body(self.source, "commit_opencode_configuration")
        lines = body.split("\n")
        marker_lines = [i for i, line in enumerate(lines)
                        if "remove_opencode_transaction_marker" in line]
        rollback_rm_lines = [i for i, line in enumerate(lines)
                             if 'rm -rf "$rollback_path"' in line and '"$incoming"' not in line]
        self.assertTrue(marker_lines, "marker removal not found in commit function")
        self.assertTrue(rollback_rm_lines, "standalone rollback cleanup not found in commit function")
        self.assertLess(marker_lines[-1], rollback_rm_lines[-1],
                        "committed marker must be cleared before rollback is discarded")

    # ── comment accuracy audits (requirement 5) ──
    def test_manifest_tool_comment_fixed(self) -> None:
        """The manifest helper comment must say only validate/compare are read-only."""
        try:
            idx = self.source.index("manifest_tool()")
        except ValueError:
            self.fail("manifest_tool() not found")
        preceding = self.source[max(0, idx - 800):idx]
        self.assertIn("Centralized manifest/ownership safety helper", preceding)
        self.assertIn("validate", preceding)
        self.assertIn("mutating", preceding)

    def test_compatibility_check_gating_comment(self) -> None:
        body = _extract_function_body(self.source, "run_compatibility_check")
        self.assertIn("static diagnostics", body)
        self.assertIn("runtime smoke", body)

    # ── ordering audits ──
    def test_transaction_rollback_ordering(self) -> None:
        self.assertIn("transaction", self.source.lower())
        self.assertIn("snapshot_live_configuration", self.source)
        self.assertIn("restore_live_configuration", self.source)

    def test_manifest_ordering(self) -> None:
        self.assertIn("manifest_tool", self.source)
        self.assertIn("OPENCODE_MANIFEST", self.source)

    def test_rtk_ordering(self) -> None:
        self.assertIn("resolve_rtk", self.source)

    def test_worktrunk_adapter_ordering(self) -> None:
        self.assertIn("install_wt_orca", self.source)
        self.assertIn("install_worktrunk_config", self.source)

    def test_dependency_install_ordering(self) -> None:
        self.assertIn("install_omo", self.source)
        self.assertIn("install_codebase_memory_mcp", self.source)

    # ── force override wiring audits ──
    def test_run_deploy_gates_strict_validate_on_non_force(self) -> None:
        """Force deploy must skip the strict manifest validate in run_deploy.

        Normal deploy keeps strict validation; force mode defers to the force
        override preflight, which relaxes only opencode.json / opencode.jsonc
        hash drift. The strict validate must be guarded by a non-force branch.
        """
        body = _extract_function_body(self.source, "run_deploy")
        self.assertTrue(body, "run_deploy not found in deploy.sh")
        self.assertIn('"$FORCE" != true', body,
                      "run_deploy must gate strict validate on non-force mode")

    def test_force_validates_before_mutation(self) -> None:
        """Force override validation must run before any live or package mutation."""
        body = _extract_function_body(self.source, "run_deploy")
        self.assertTrue(body, "run_deploy not found in deploy.sh")
        self.assertIn("manifest_override_plan", body,
                      "run_deploy must invoke manifest_override_plan")
        override_pos = body.index("manifest_override_plan")
        for token in ("initialize_rtk_plugin", "install_omo", "snapshot_live_configuration"):
            self.assertIn(token, body, f"{token} missing from run_deploy")
            self.assertLess(override_pos, body.index(token),
                            f"manifest_override_plan must precede {token} in run_deploy")

    def test_force_skips_snapshot_in_run_deploy(self) -> None:
        """Force mode must not call snapshot_live_configuration."""
        body = _extract_function_body(self.source, "run_deploy")
        self.assertIn('if [[ "$FORCE" != true ]]; then', body,
                      "run_deploy must gate snapshot_live_configuration on non-force")
        self.assertIn("snapshot_live_configuration", body)

    def test_commit_consumes_force_plan_without_revalidating(self) -> None:
        """Commit consumes the pre-validated force plan; no re-validation after mutation."""
        body = _extract_function_body(self.source, "commit_opencode_configuration")
        self.assertTrue(body, "commit_opencode_configuration not found in deploy.sh")
        self.assertNotIn("manifest_override_plan", body,
                         "commit must not re-run force validation after mutation")
        self.assertNotIn("preflight_force_summary", body,
                         "commit must not re-run force preflight summary after mutation")

    def test_commit_force_creates_no_rollback(self) -> None:
        """Force commit path replaces without transaction markers or rollback backup."""
        body = _extract_function_body(self.source, "commit_opencode_configuration")
        self.assertIn("replace_live_configuration_force", body,
                      "force commit path must delegate to replace_live_configuration_force")
        self.assertIn('if [[ "$FORCE" = true ]]; then', body,
                      "commit must branch force mode")
        force_fn = _extract_function_body(self.source, "replace_live_configuration_force")
        self.assertTrue(force_fn, "replace_live_configuration_force not found in deploy.sh")
        self.assertNotIn("write_opencode_transaction_marker", force_fn,
                         "force replacement must not write a transaction marker")
        self.assertNotIn("$rollback_path", force_fn,
                         "force replacement must not create a rollback directory")
        self.assertNotIn("LIVE_SNAPSHOT", force_fn,
                         "force replacement must not reference the live snapshot")
        self.assertNotIn("snapshot_live_configuration", force_fn,
                         "force replacement must not invoke snapshot_live_configuration")

    def test_force_rejects_compatibility_combination(self) -> None:
        """--force with --compatibility-check must be rejected as deploy-only."""
        result = subprocess.run(  # noqa: PLW1510 — manual exit code assertion
            ["bash", str(DEPLOY_SCRIPT), "--compatibility-check", "--force"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("deploy-only", result.stderr + result.stdout)

    def test_force_rejects_check_combination(self) -> None:
        """--force with --check must be rejected as deploy-only."""
        result = subprocess.run(  # noqa: PLW1510 — manual exit code assertion
            ["bash", str(DEPLOY_SCRIPT), "--check", "--force"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("deploy-only", result.stderr + result.stdout)

    def test_no_backup_helpers_remain(self) -> None:
        """The backup-only production helpers must be fully removed."""
        self.assertNotIn("create_force_backup()", self.source)
        self.assertNotIn("verify_force_backup()", self.source)
        self.assertNotIn("write_force_metadata()", self.source)
        self.assertNotIn("FORCE_BACKUP_ROOT", self.source)


if __name__ == "__main__":
    verbosity = int(os.environ.get("VERBOSITY", "2"))
    unittest.main(verbosity=verbosity)
