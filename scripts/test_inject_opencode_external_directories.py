import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("inject-opencode-external-directories.py")
SPEC = importlib.util.spec_from_file_location("inject_opencode_external_directories", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


PATTERNS = [
    "/Users/guilhermebomfim/developer/planning-docs/*/.planning/**/*",
    "~/developer/planning-docs/*/.planning/**/*",
    "/Users/guilhermebomfim/project-workspaces/**/*",
    "~/developer/planning-docs/*/*/prs/**/*",
    "/Users/guilhermebomfim/developer/planning-docs/*/*/prs/**/*",
]
SCHEMA = '"$schema": "https://opencode.ai/config.json"'


class InjectExternalDirectoriesTests(unittest.TestCase):
    def test_canonical_patterns_are_exact(self) -> None:
        self.assertEqual(tuple(PATTERNS), MODULE.CANONICAL_EXTERNAL_DIRECTORIES)
        self.assertIn("/Users/guilhermebomfim/project-workspaces/**/*", MODULE.CANONICAL_EXTERNAL_DIRECTORIES)

    def test_rejects_arbitrary_patterns_before_reading_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "does-not-exist.jsonc"
            with self.assertRaisesRegex(MODULE.InjectionError, "exactly match"):
                MODULE.inject(path, ["*"])

    def test_adds_permission_to_schema_less_empty_root(self) -> None:
        source = "{}"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            MODULE.inject(path, PATTERNS)
            result = path.read_text(encoding="utf-8")
            self.assertIn(SCHEMA, result)
            self.assertIn('"permission": {', result)
            for pattern in PATTERNS:
                self.assertIn(f'{pattern!r}'.replace("'", '"') + ': "allow"', result)

    def test_adds_external_directory_to_empty_permission(self) -> None:
        source = '{"permission": {}}'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            MODULE.inject(path, PATTERNS)
            result = path.read_text(encoding="utf-8")
            self.assertIn(SCHEMA, result)
            self.assertIn('"external_directory": {', result)

    def test_schema_less_leading_comment_and_crlf_root_preserve_source(self) -> None:
        source = "\r\n// $schema is intentionally mentioned in this comment\r\n{\r\n\t\"model\": \"preserved\"\r\n}\r\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(source)
            MODULE.inject(path, PATTERNS)
            with path.open("r", encoding="utf-8", newline="") as handle:
                result = handle.read()
            self.assertTrue(result.startswith("\r\n// $schema is intentionally mentioned in this comment\r\n{"))
            self.assertIn('\t"model": "preserved"', result)
            self.assertIn(SCHEMA, result)
            self.assertNotIn("\n", result.replace("\r\n", ""))

    def test_rejects_malformed_jsonc_branches_without_mutating(self) -> None:
        malformed = {
            "unterminated object": '{"permission": {',
            "unterminated array": '{"permission": {"external_directory": [',
            "unterminated comment": '{"permission": { /*',
            "missing comma": '{"permission": {"external_directory": {"safe": "allow" "other": "allow"}}}',
            "missing colon": '{"permission": {"external_directory": {"safe" "allow"}}}',
            "invalid key": '{1: "value"}',
            "invalid value": '{"value": @}',
            "non-object root": '[]',
        }
        for name, source in malformed.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "opencode.jsonc"
                path.write_text(source, encoding="utf-8")
                with self.assertRaises(MODULE.InjectionError):
                    MODULE.inject(path, PATTERNS)
                self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_rejects_trailing_non_whitespace(self) -> None:
        source = '{"$schema": "https://opencode.ai/config.json"} trailing'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            with self.assertRaises(MODULE.InjectionError):
                MODULE.inject(path, PATTERNS)
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_rejects_duplicate_keys(self) -> None:
        source = '{%s, "permission": {"external_directory": {"safe": "allow", "safe": "deny"}}}' % SCHEMA
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(MODULE.InjectionError, "duplicate"):
                MODULE.inject(path, PATTERNS)

    def test_rejects_existing_canonical_conflict(self) -> None:
        source = '{%s, "permission": {"external_directory": {"%s": "deny"}}}' % (SCHEMA, PATTERNS[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(MODULE.InjectionError, "conflicts"):
                MODULE.inject(path, PATTERNS)

    def test_rejects_noncanonical_allow_rule_but_preserves_denies(self) -> None:
        source = '{%s, "permission": {"external_directory": {"*": "allow", "safe": "deny"}}}' % SCHEMA
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(MODULE.InjectionError, "outside the canonical list"):
                MODULE.inject(path, PATTERNS)
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_rejects_nan_and_infinity(self) -> None:
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                source = '{%s, "permission": {"external_directory": {"safe": %s}}}' % (SCHEMA, constant)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "opencode.jsonc"
                    path.write_text(source, encoding="utf-8")
                    with self.assertRaisesRegex(MODULE.InjectionError, "invalid JSONC constant"):
                        MODULE.inject(path, PATTERNS)

    def test_cli_reports_invalid_utf8_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_bytes(b'{"permission": \xff}')
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), *PATTERNS],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_rejects_duplicate_patterns_without_mutation(self) -> None:
        source = '{%s}' % SCHEMA
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), PATTERNS[0], PATTERNS[0], *PATTERNS[1:]],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_cli_reports_excessive_nesting_without_traceback(self) -> None:
        source = '{"nested": ' + ("[" * (MODULE.MAX_PARSE_DEPTH + 2)) + "0" + ("]" * (MODULE.MAX_PARSE_DEPTH + 2)) + "}"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), *PATTERNS],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("nesting exceeds", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_injection_is_idempotent_and_preserves_jsonc_content(self) -> None:
        source = """{
  // Keep this comment.
  \"$schema\": \"https://opencode.ai/config.json\",
  \"permission\": {
    \"external_directory\": {
      \"safe\": \"deny\"
    }
  },
  \"model\": \"preserved\"
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opencode.jsonc"
            path.write_text(source, encoding="utf-8")
            MODULE.inject(path, PATTERNS)
            first = path.read_text(encoding="utf-8")
            MODULE.inject(path, PATTERNS)
            self.assertEqual(path.read_text(encoding="utf-8"), first)
            self.assertIn("// Keep this comment.", first)
            self.assertIn('"safe": "deny"', first)
            self.assertIn('"model": "preserved"', first)
            for pattern in PATTERNS:
                self.assertIn(f'{pattern!r}'.replace("'", '"') + ': "allow"', first)


if __name__ == "__main__":
    unittest.main()
