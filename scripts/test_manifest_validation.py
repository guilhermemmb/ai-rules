#!/usr/bin/env python3
"""Focused tests for the OpenCode ownership manifest diagnostics.

These tests exercise the real Validator.manifest validation path (not a
re-implementation) against temporary manifests/config trees, and never touch
the live home configuration. Coverage:

1. Multiple changed files are all reported in a single run.
2. A matching file is not reported.
3. A missing file is reported with a ``missing`` status and ``<missing>`` actual.
4. A symlink is reported with a ``symlink`` status and ``<symlink>`` actual.
5. A non-regular path is reported with ``not-regular`` and ``<not-regular>``.
6. Diagnostics never leak file contents or secrets.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VALIDATOR_PATH = _HERE / "validate-ai-rules.py"
_DEPLOY_SCRIPT = _HERE.parent / "deploy.sh"

_validator_spec = importlib.util.spec_from_file_location(
    "validate_ai_rules", _VALIDATOR_PATH
)
_validator_module = importlib.util.module_from_spec(_validator_spec)
sys.modules["validate_ai_rules"] = _validator_module
_validator_spec.loader.exec_module(_validator_module)

Validator = _validator_module.Validator

_OPENCODE_MANAGED_BY = "ai-rules/deploy.sh"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ManifestValidationTests(unittest.TestCase):
    """Deterministic manifest-diagnostic tests on isolated temporary trees."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="manifest-validation-")
        self.addCleanup(self._tmp.cleanup)
        self.config_dir = Path(self._tmp.name) / "opencode"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.config_dir / ".ai-rules.manifest.json"

    def _write_file(self, relative: str, content: str) -> Path:
        path = self.config_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _write_manifest(self, files_hashes: dict[str, str]) -> None:
        payload = {
            "managed_by": _OPENCODE_MANAGED_BY,
            "version": 1,
            "timestamp": "2026-09-02T00:00:00+00:00",
            "managed_files": sorted(files_hashes),
            "managed_directories": [],
            "managed_file_hashes": dict(sorted(files_hashes.items())),
        }
        self.manifest_path.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def _validate(self) -> list[str]:
        validator = Validator(
            root=self.config_dir, payload=None, opencode_config=None
        )
        validator.validate_opencode_manifest(
            self.manifest_path, self.config_dir, require_present=True
        )
        return list(validator.errors)

    def _diagnostics(self, errors: list[str]) -> dict[str, tuple[str, str, str]]:
        """Map managed path -> (status, expected_sha256, actual_sha256)."""
        diagnostics: dict[str, tuple[str, str, str]] = {}
        pattern = re.compile(
            r"manifest managed file (?P<status>\S+): path=(?P<path>\S+) "
            r"expected_sha256=(?P<expected>\S+) actual_sha256=(?P<actual>\S+)"
        )
        for error in errors:
            match = pattern.search(error)
            if match is None:
                continue
            diagnostics[match.group("path")] = (
                match.group("status"),
                match.group("expected"),
                match.group("actual"),
            )
        return diagnostics

    def test_multiple_changed_files_reported_in_one_run(self) -> None:
        self._write_file("a.txt", "original-a")
        self._write_file("b.txt", "original-b")
        self._write_manifest(
            {
                "a.txt": _sha256_text("stale-a"),
                "b.txt": _sha256_text("stale-b"),
            }
        )

        errors = self._validate()
        diagnostics = self._diagnostics(errors)

        self.assertIn("a.txt", diagnostics)
        self.assertIn("b.txt", diagnostics)
        for relative in ("a.txt", "b.txt"):
            status, expected, actual = diagnostics[relative]
            self.assertEqual(status, "changed")
            self.assertEqual(expected, _sha256_text(f"stale-{relative[0]}"))
            self.assertEqual(
                actual,
                _sha256_text(f"original-{relative[0]}"),
            )
        # One error per mismatch, and no unrelated errors.
        self.assertEqual(len(diagnostics), 2)
        self.assertEqual(len(errors), 2)

    def test_matching_file_not_reported(self) -> None:
        self._write_file("ok.txt", "unchanged")
        self._write_manifest({"ok.txt": _sha256_text("unchanged")})

        errors = self._validate()

        self.assertEqual(errors, [])
        self.assertEqual(self._diagnostics(errors), {})

    def test_missing_file_reported(self) -> None:
        self._write_manifest({"gone.txt": _sha256_text("was-here")})

        errors = self._validate()
        diagnostics = self._diagnostics(errors)

        self.assertIn("gone.txt", diagnostics)
        status, expected, actual = diagnostics["gone.txt"]
        self.assertEqual(status, "missing")
        self.assertEqual(expected, _sha256_text("was-here"))
        self.assertEqual(actual, "<missing>")

    def test_symlink_reported(self) -> None:
        self._write_file("real.txt", "target-content")
        os.symlink("real.txt", self.config_dir / "link.txt")
        self._write_manifest({"link.txt": _sha256_text("stale-link")})

        errors = self._validate()
        diagnostics = self._diagnostics(errors)

        self.assertIn("link.txt", diagnostics)
        status, expected, actual = diagnostics["link.txt"]
        self.assertEqual(status, "symlink")
        self.assertEqual(expected, _sha256_text("stale-link"))
        self.assertEqual(actual, "<symlink>")

    def test_non_regular_path_reported(self) -> None:
        # A directory where a managed file is expected is a non-regular path.
        (self.config_dir / "as-dir").mkdir(parents=True, exist_ok=True)
        self._write_manifest({"as-dir": _sha256_text("stale-dir")})

        errors = self._validate()
        diagnostics = self._diagnostics(errors)

        self.assertIn("as-dir", diagnostics)
        status, expected, actual = diagnostics["as-dir"]
        self.assertEqual(status, "not-regular")
        self.assertEqual(expected, _sha256_text("stale-dir"))
        self.assertEqual(actual, "<not-regular>")

    def test_no_secret_or_content_leakage(self) -> None:
        secret = "SECRET_API_KEY=deadbeef1234cafe"
        self._write_file("secret.txt", f"staging {secret}\n")
        self._write_manifest({"secret.txt": _sha256_text("expected-only")})

        errors = self._validate()
        joined = "\n".join(errors)

        # The diagnostic must expose hashes and status, never the payload.
        self.assertIn("changed", joined)
        self.assertIn("expected_sha256=", joined)
        self.assertIn("actual_sha256=", joined)
        self.assertNotIn(secret, joined)
        self.assertNotIn("staging", joined)


def _extract_function_body(source: str, func_name: str) -> str:
    """Extract the body of a shell function between ``func_name()`` and ``}``."""
    pattern = rf"^{func_name}\(\)\s*\{{"
    match = re.search(pattern, source, re.MULTILINE)
    if not match:
        return ""
    start = match.start()
    brace = 0
    in_func = False
    for idx, char in enumerate(source[start:], start):
        if char == "{":
            brace += 1
            in_func = True
        elif char == "}":
            brace -= 1
            if in_func and brace == 0:
                return source[start : idx + 1]
    return ""


def _extract_embedded_python(func_name: str) -> str:
    """Extract the ``<<'PY' ... PY`` Python from a deploy.sh shell function.

    Mirrors the extraction used by test_deploy_compatibility.py so the tests
    exercise the real production manifest tool rather than a re-implementation.
    """
    source = _DEPLOY_SCRIPT.read_text()
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


def _threshold_constant(name: str) -> int:
    """Return an integer constant from deploy.sh's embedded manifest Python.

    The value is extracted from the real deploy.sh source so the oversized-file
    tests track the actual production bounds rather than a duplicated copy.
    """
    source = _DEPLOY_SCRIPT.read_text()
    match = re.search(
        rf"^{name}\s*=\s*([0-9][0-9_]*)\s*(?:#.*)?$", source, re.MULTILINE
    )
    assert match is not None, f"{name} not found in deploy.sh"
    return int(match.group(1).replace("_", ""))


def _write_python_stub(source: str, name: str = "manifest_drift_") -> Path:
    fd, path = tempfile.mkstemp(suffix=".py", prefix=name)
    os.close(fd)
    stub = Path(path)
    stub.write_text(source)
    return stub


class ManifestDriftReportTests(unittest.TestCase):
    """Exercise the real manifest_tool ``drift-report`` operation.

    These tests extract the production Python embedded in ``manifest_tool()``
    from deploy.sh (not a re-implementation) and run it against isolated
    temporary live/staged roots. They never touch the live home configuration.
    """

    @classmethod
    def setUpClass(cls) -> None:
        source = _extract_embedded_python("manifest_tool")
        if not source:
            raise unittest.SkipTest(
                "could not extract manifest_tool Python from deploy.sh"
            )
        cls.manifest_py = _write_python_stub(source)
        cls.addClassCleanup(os.unlink, cls.manifest_py)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="drift-report-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.staged = self.root / "staged"
        self.live = self.root / "live"
        self.staged.mkdir(parents=True, exist_ok=True)
        self.live.mkdir(parents=True, exist_ok=True)

    def _run(self) -> dict:
        result = subprocess.run(  # noqa: PLW1510 — manual exit assertion below
            [
                "python3",
                str(self.manifest_py),
                "drift-report",
                str(self.staged),
                str(self.live),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def _write(self, root: Path, relative: str, content: bytes | str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def _entries(self, report: dict) -> dict[str, dict]:
        return {entry["path"]: entry for entry in report["entries"]}

    def test_equal_files_reported_identical(self) -> None:
        for relative in ("opencode.json", "opencode.jsonc"):
            self._write(self.staged, relative, '{"a": 1}\n')
            self._write(self.live, relative, '{"a": 1}\n')

        report = self._run()
        entries = self._entries(report)

        self.assertEqual(
            report["mutable_drift_paths"], ["opencode.json", "opencode.jsonc"]
        )
        for relative in ("opencode.json", "opencode.jsonc"):
            entry = entries[relative]
            self.assertEqual(entry["status"], "identical")
            self.assertEqual(entry["live_sha256"], entry["staged_sha256"])
            self.assertIsNone(entry["diff"])

    def test_changed_file_reported_with_redacted_diff(self) -> None:
        secret = "SECRET_API_KEY=deadbeef1234cafe"
        self._write(self.staged, "opencode.json", '{"version": 2}\n')
        self._write(
            self.live, "opencode.json", f'{{"version": 1, "key": "{secret}"}}\n'
        )

        report = self._run()
        entry = self._entries(report)["opencode.json"]

        self.assertEqual(entry["status"], "changed")
        self.assertNotEqual(entry["live_sha256"], entry["staged_sha256"])
        self.assertIsNotNone(entry["diff"])
        # The diff is a unified text diff (file labels + hunk header) with
        # redacted content lines.
        self.assertIn("--- opencode.json (live)", entry["diff"])
        self.assertIn("+++ opencode.json (staged)", entry["diff"])
        self.assertIn("@@", entry["diff"])
        self.assertIn("<redacted>", entry["diff"])
        # Never leak content or secrets.
        self.assertNotIn(secret, entry["diff"])
        self.assertNotIn("version", entry["diff"])
        self.assertNotIn("key", entry["diff"])

    def test_missing_file_reported(self) -> None:
        self._write(self.staged, "opencode.json", '{"a": 1}\n')
        self._write(self.staged, "opencode.jsonc", '{"b": 2}\n')
        self._write(self.live, "opencode.json", '{"a": 1}\n')
        # live opencode.jsonc is absent.

        report = self._run()
        entries = self._entries(report)

        self.assertEqual(entries["opencode.json"]["status"], "identical")
        self.assertEqual(entries["opencode.jsonc"]["status"], "missing-live")
        self.assertIsNone(entries["opencode.jsonc"]["live_sha256"])
        self.assertIsNotNone(entries["opencode.jsonc"]["staged_sha256"])
        self.assertIsNone(entries["opencode.jsonc"]["diff"])

    def test_binary_file_reported_hashes_only(self) -> None:
        marker = "CONTENTMARKER"
        self._write(self.staged, "opencode.json", '{"a": 1}\n')
        self._write(self.live, "opencode.json", '{"a": 1}\n')
        self._write(
            self.staged, "opencode.jsonc", b"\x00\x01\x02" + marker.encode() + b"\xff"
        )
        self._write(
            self.live, "opencode.jsonc", b"\x00\x01\x02other\xfe"
        )

        report = self._run()
        entry = self._entries(report)["opencode.jsonc"]

        self.assertEqual(entry["status"], "binary")
        self.assertIsNotNone(entry["live_sha256"])
        self.assertIsNotNone(entry["staged_sha256"])
        self.assertIsNone(entry["diff"])
        # The report must never include raw binary contents.
        self.assertNotIn(marker, json.dumps(report, sort_keys=True))

    def test_multi_file_reported_deterministically(self) -> None:
        self._write(self.staged, "opencode.json", '{"v": 2}\n')
        self._write(self.live, "opencode.json", '{"v": 1}\n')
        self._write(self.staged, "opencode.jsonc", '{"w": 2}\n')
        self._write(self.live, "opencode.jsonc", '{"w": 1}\n')

        report = self._run()

        self.assertEqual(
            [entry["path"] for entry in report["entries"]],
            ["opencode.json", "opencode.jsonc"],
        )
        self.assertEqual(
            report["mutable_drift_paths"], ["opencode.json", "opencode.jsonc"]
        )
        for entry in report["entries"]:
            self.assertEqual(entry["status"], "changed")
            self.assertIsNotNone(entry["diff"])

    def test_report_is_secret_and_content_free(self) -> None:
        secret = "sk-live-super-secret-token-1234567890"
        self._write(self.staged, "opencode.json", '{"version": 1}\n')
        self._write(self.live, "opencode.json", f'{{"apiKey": "{secret}"}}\n')
        self._write(self.staged, "opencode.jsonc", '{"version": 1}\n')
        self._write(self.live, "opencode.jsonc", f'{{"token": "{secret}"}}\n')

        report = self._run()
        serialized = json.dumps(report, sort_keys=True)

        self.assertNotIn(secret, serialized)
        self.assertNotIn("apiKey", serialized)
        self.assertNotIn("token", serialized)
        self.assertNotIn("super-secret", serialized)

    def test_header_like_content_redacted(self) -> None:
        # A removed line whose content begins with "--" produces a diff line
        # prefixed "---"; an added line whose content begins with "++" produces
        # a diff line prefixed "+++". Only the genuine file headers (lines 0
        # and 1) may remain visible; these header-like content lines must be
        # redacted and never leak.
        self._write(self.staged, "opencode.json", "++ staged-only-secret\ncommon\n")
        self._write(self.live, "opencode.json", "-- live-only-secret\ncommon\n")
        self._write(self.staged, "opencode.jsonc", '{"w": 1}\n')
        self._write(self.live, "opencode.jsonc", '{"w": 1}\n')

        report = self._run()
        entry = self._entries(report)["opencode.json"]

        self.assertEqual(entry["status"], "changed")
        diff = entry["diff"]
        self.assertIsNotNone(diff)
        # Genuine generated file headers survive.
        self.assertIn("--- opencode.json (live)", diff)
        self.assertIn("+++ opencode.json (staged)", diff)
        # Content lines are redacted down to their +/- marker.
        self.assertIn("-<redacted>", diff)
        self.assertIn("+<redacted>", diff)
        # Header-like content never leaks.
        self.assertNotIn("live-only-secret", diff)
        self.assertNotIn("staged-only-secret", diff)

    def test_oversized_by_bytes_hash_only(self) -> None:
        max_bytes = _threshold_constant("DRIFT_DIFF_MAX_BYTES")
        self._write(self.staged, "opencode.json", '{"a": 1}\n')
        self._write(
            self.live, "opencode.json", b"a" * max_bytes + b"BYTE_SECRET_MARKER"
        )
        self._write(self.staged, "opencode.jsonc", '{"b": 2}\n')
        self._write(self.live, "opencode.jsonc", '{"b": 2}\n')

        report = self._run()
        entry = self._entries(report)["opencode.json"]

        self.assertEqual(entry["status"], "oversized")
        self.assertIsNotNone(entry["live_sha256"])
        self.assertIsNotNone(entry["staged_sha256"])
        self.assertIsNone(entry["diff"])
        self.assertNotIn("BYTE_SECRET_MARKER", json.dumps(report, sort_keys=True))

    def test_oversized_by_lines_hash_only(self) -> None:
        max_lines = _threshold_constant("DRIFT_DIFF_MAX_LINES")
        self._write(self.staged, "opencode.json", '{"a": 1}\n')
        self._write(
            self.live,
            "opencode.json",
            "LINE_SECRET_MARKER\n" * (max_lines + 1),
        )
        self._write(self.staged, "opencode.jsonc", '{"b": 2}\n')
        self._write(self.live, "opencode.jsonc", '{"b": 2}\n')

        report = self._run()
        entry = self._entries(report)["opencode.json"]

        self.assertEqual(entry["status"], "oversized")
        self.assertIsNotNone(entry["live_sha256"])
        self.assertIsNotNone(entry["staged_sha256"])
        self.assertIsNone(entry["diff"])
        self.assertNotIn("LINE_SECRET_MARKER", json.dumps(report, sort_keys=True))


class PreflightForceSummaryAuditTests(unittest.TestCase):
    """Source audits for the human-readable force preflight summary.

    ``preflight_force_summary`` must delegate to the redacted drift-report
    operation and must never emit raw unified-diff file contents.
    """

    def test_preflight_delegates_to_drift_report(self) -> None:
        source = _DEPLOY_SCRIPT.read_text()
        body = _extract_function_body(source, "preflight_force_summary")
        self.assertTrue(body, "preflight_force_summary not found in deploy.sh")
        self.assertIn(
            "manifest_tool drift-report",
            body,
            "preflight_force_summary must delegate to the drift-report operation",
        )
        self.assertNotIn(
            "diff -u",
            body,
            "preflight_force_summary must not emit raw `diff -u` file contents",
        )


if __name__ == "__main__":
    verbosity = int(os.environ.get("VERBOSITY", "2"))
    unittest.main(verbosity=verbosity)
