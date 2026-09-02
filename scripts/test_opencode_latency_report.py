#!/usr/bin/env python3
"""Deterministic tests for the local OpenCode latency reporter."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("opencode-latency-report.py")
SPEC = importlib.util.spec_from_file_location("opencode_latency_report", SCRIPT_PATH)
assert SPEC and SPEC.loader
reporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reporter
SPEC.loader.exec_module(reporter)


class ReporterTest(unittest.TestCase):
    BASE_TIME_MS = 1_700_000_000_000

    def _database(self, schema: str, rows: list[tuple[str, tuple[object, ...]]]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "synthetic.db"
        connection = sqlite3.connect(path)
        connection.executescript(schema)
        for statement, values in rows:
            connection.execute(statement, values)
        connection.commit()
        connection.close()
        return path

    def test_normal_session_and_json_shape(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER,
                                  time_completed INTEGER, data TEXT);
            CREATE TABLE part (id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("session-1", self.BASE_TIME_MS, self.BASE_TIME_MS + 2_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
                    (
                        "message-user",
                        "session-1",
                        self.BASE_TIME_MS,
                        self.BASE_TIME_MS + 50,
                        json.dumps(
                            {
                                "role": "user",
                                "time": {
                                    "start": self.BASE_TIME_MS,
                                    "end": self.BASE_TIME_MS + 50,
                                },
                                "prompt": "must not be emitted",
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
                    (
                        "message-1",
                        "session-1",
                        self.BASE_TIME_MS + 100,
                        self.BASE_TIME_MS + 1_900,
                        json.dumps(
                            {
                                "role": "assistant",
                                "agent": "fixer",
                                "modelID": "bf-o/gpt-5.6-luna",
                                "providerID": "bf-o",
                                "time": {
                                    "start": self.BASE_TIME_MS + 200,
                                    "end": self.BASE_TIME_MS + 1_800,
                                },
                                "tokens": {"input": 10, "output": 20},
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO part VALUES (?, ?, ?, ?)",
                    (
                        "part-1",
                        "session-1",
                        self.BASE_TIME_MS + 300,
                        json.dumps({"type": "text"}),
                    ),
                ),
            ],
        )
        report = reporter.generate_report(
            path, now=self.BASE_TIME_MS / 1000 + 10, since="1h"
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(report["database"]["read_only"])
        self.assertEqual(report["aggregate"]["session_count"], 1)
        self.assertEqual(report["sessions"][0]["wall_duration_ms"], 2_000)
        self.assertEqual(report["sessions"][0]["agents"], ["fixer"])
        self.assertEqual(report["sessions"][0]["tokens"]["input"], 10)
        self.assertEqual(report["sessions"][0]["timing"]["ttft_ms_approx"], 150)
        self.assertIn("sessions", report)
        self.assertIn("warnings", report)

    def test_tool_timing_and_mcp_counts(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            CREATE TABLE part (id TEXT, session_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("s", self.BASE_TIME_MS, self.BASE_TIME_MS + 3_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    ("m", "s", json.dumps({"role": "assistant", "model": "model-a"})),
                ),
                (
                    "INSERT INTO part VALUES (?, ?, ?)",
                    (
                        "p",
                        "s",
                        json.dumps(
                            {
                                "type": "tool",
                                "tool": "mcp__github__search",
                                "state": {
                                    "status": "completed",
                                    "time": {
                                        "start": self.BASE_TIME_MS + 500,
                                        "end": self.BASE_TIME_MS + 1_250,
                                    },
                                    "input": "MUST NOT APPEAR",
                                    "output": "MUST NOT APPEAR",
                                },
                            }
                        ),
                    ),
                ),
            ],
        )
        report = reporter.generate_report(path, now=self.BASE_TIME_MS / 1000 + 10_000)
        session = report["sessions"][0]
        self.assertEqual(session["tools"]["count"], 1)
        self.assertEqual(session["tools"]["duration_ms_approx"], 750)
        self.assertEqual(session["mcp"]["count"], 1)
        self.assertEqual(report["aggregate"]["mcp"]["count"], 1)

    def test_cache_fields_are_aggregated(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("s", self.BASE_TIME_MS, self.BASE_TIME_MS + 1_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "m",
                        "s",
                        json.dumps(
                            {
                                "role": "assistant",
                                "tokens": {
                                    "input": 100,
                                    "output": 50,
                                    "cache": {"read": 80, "write": 7},
                                },
                            }
                        ),
                    ),
                ),
            ],
        )
        tokens = reporter.generate_report(path)["sessions"][0]["tokens"]
        self.assertEqual(tokens, {"input": 100, "output": 50, "cache_read": 80, "cache_write": 7})

    def test_mixed_message_and_part_tokens_merge_per_metric(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            CREATE TABLE part (id TEXT, session_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("mixed", self.BASE_TIME_MS, self.BASE_TIME_MS + 1_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "m",
                        "mixed",
                        json.dumps(
                            {
                                "role": "assistant",
                                "tokens": {"input": 10, "cache": {"read": 2}},
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO part VALUES (?, ?, ?)",
                    (
                        "p1",
                        "mixed",
                        json.dumps(
                            {
                                "type": "step-finish",
                                "tokens": {
                                    "input": 99,
                                    "output": 20,
                                    "cache": {"read": 99, "write": 4},
                                },
                            }
                        ),
                    ),
                ),
            ],
        )
        tokens = reporter.generate_report(path)["sessions"][0]["tokens"]
        self.assertEqual(tokens, {"input": 10, "output": 20, "cache_read": 2, "cache_write": 4})

    def test_message_linked_parts_resolve_session_and_assistant_role(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            CREATE TABLE part (id TEXT, message_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("message-linked", self.BASE_TIME_MS, self.BASE_TIME_MS + 2_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "user-message",
                        "message-linked",
                        json.dumps(
                            {
                                "role": "user",
                                "time": {
                                    "start": self.BASE_TIME_MS,
                                    "end": self.BASE_TIME_MS + 100,
                                },
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "assistant-message",
                        "message-linked",
                        json.dumps(
                            {
                                "role": "assistant",
                                "agent": "fixer",
                                "model": "model-a",
                                "tokens": {"input": 2},
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO part VALUES (?, ?, ?)",
                    (
                        "text-part",
                        "assistant-message",
                        json.dumps(
                            {
                                "type": "text",
                                "time": {"start": self.BASE_TIME_MS + 200},
                                "tokens": {"output": 3},
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO part VALUES (?, ?, ?)",
                    (
                        "tool-part",
                        "assistant-message",
                        json.dumps(
                            {
                                "type": "tool",
                                "tool": "mcp__github__search",
                                "state": {
                                    "time": {
                                        "start": self.BASE_TIME_MS + 300,
                                        "end": self.BASE_TIME_MS + 700,
                                    }
                                },
                            }
                        ),
                    ),
                ),
            ],
        )
        report = reporter.generate_report(path)
        self.assertEqual(len(report["sessions"]), 1)
        session = report["sessions"][0]
        self.assertEqual(session["tokens"]["input"], 2)
        self.assertEqual(session["tokens"]["output"], 3)
        self.assertEqual(session["tools"]["count"], 1)
        self.assertEqual(session["tools"]["duration_ms_approx"], 400)
        self.assertEqual(session["mcp"]["count"], 1)
        self.assertEqual(session["timing"]["ttft_ms_approx"], 100)
        self.assertFalse(any("part metadata was skipped" in warning for warning in report["warnings"]))

    def test_reversed_model_and_tool_timestamps_are_ignored(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            CREATE TABLE part (id TEXT, session_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("reversed", self.BASE_TIME_MS, self.BASE_TIME_MS + 4_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "m",
                        "reversed",
                        json.dumps(
                            {
                                "role": "assistant",
                                "time": {
                                    "start": self.BASE_TIME_MS + 3_000,
                                    "end": self.BASE_TIME_MS + 2_000,
                                },
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO part VALUES (?, ?, ?)",
                    (
                        "p",
                        "reversed",
                        json.dumps(
                            {
                                "type": "tool",
                                "tool": "safe_tool",
                                "time": {
                                    "start": self.BASE_TIME_MS + 2_000,
                                    "end": self.BASE_TIME_MS + 1_000,
                                },
                            }
                        ),
                    ),
                ),
            ],
        )
        report = reporter.generate_report(path)
        session = report["sessions"][0]
        self.assertIsNone(session["timing"]["model_duration_ms_approx"])
        self.assertIsNone(session["timing"]["ttft_ms_approx"])
        self.assertEqual(session["tools"]["duration_ms_approx"], 0)
        self.assertTrue(any("reversed" in unknown for unknown in session["unknowns"]))
        self.assertGreaterEqual(report["aggregate"]["latency_ms"]["wall"]["p50"], 0)

    def test_ttft_uses_assistant_output_after_user_turn(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("ttft", self.BASE_TIME_MS, self.BASE_TIME_MS + 2_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "user",
                        "ttft",
                        json.dumps(
                            {
                                "role": "user",
                                "time": {
                                    "start": self.BASE_TIME_MS + 100,
                                    "end": self.BASE_TIME_MS + 300,
                                },
                                "prompt": "ignored user prompt",
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "assistant",
                        "ttft",
                        json.dumps(
                            {
                                "role": "assistant",
                                "model": "model-a",
                                "time": {
                                    "start": self.BASE_TIME_MS + 700,
                                    "end": self.BASE_TIME_MS + 1_200,
                                },
                            }
                        ),
                    ),
                ),
            ],
        )
        session = reporter.generate_report(path)["sessions"][0]
        self.assertEqual(session["timing"]["ttft_ms_approx"], 400)
        self.assertNotEqual(session["timing"]["ttft_ms_approx"], 100)

    def test_account_and_email_identifiers_are_excluded(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, account_id TEXT, email TEXT,
                                  time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, account_id TEXT,
                                  email TEXT, data TEXT);
            CREATE TABLE account_data (id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
                    (
                        "account-123",
                        "control-account-456",
                        "person@example.com",
                        self.BASE_TIME_MS,
                        self.BASE_TIME_MS + 1_000,
                    ),
                ),
                (
                    "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
                    (
                        "safe-session",
                        "control-account-456",
                        "person@example.com",
                        self.BASE_TIME_MS,
                        self.BASE_TIME_MS + 1_000,
                    ),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
                    (
                        "message-1",
                        "person@example.com",
                        "account-123",
                        "person@example.com",
                        json.dumps(
                            {
                                "role": "assistant",
                                "agent": "agent@example.com",
                                "model": "account-scoped-model-123",
                                "tool": "person@example.com",
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
                    (
                        "message-2",
                        "safe-session",
                        "account-123",
                        "person@example.com",
                        json.dumps(
                            {
                                "role": "assistant",
                                "agent": "agent@example.com",
                                "model": "account-scoped-model-123",
                                "provider": "safe-provider",
                                "prompt": "SECRET_RAW_PROMPT",
                                "source": "SECRET_SOURCE_CODE",
                            }
                        ),
                    ),
                ),
            ],
        )
        report = reporter.generate_report(path)
        self.assertEqual(len(report["sessions"]), 1)
        serialized = json.dumps(report)
        for value in (
            "account-123",
            "control-account-456",
            "person@example.com",
            "account-scoped-model-123",
        ):
            self.assertNotIn(value, serialized)

    def test_credential_shaped_identifiers_are_excluded(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, agent TEXT, model TEXT,
                                  provider TEXT, data TEXT);
            CREATE TABLE part (id TEXT, session_id TEXT, tool TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("credential-test", self.BASE_TIME_MS, self.BASE_TIME_MS + 1_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "message-1",
                        "credential-test",
                        "ghp_1234567890abcdef",
                        "xoxb-1234567890abcdef",
                        "AKIA1234567890ABCD",
                        json.dumps(
                            {
                                "role": "assistant",
                                "agent": "sk_live_1234567890",
                                "model": "rk_test_1234567890",
                                "provider": "glpat-1234567890",
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO part VALUES (?, ?, ?, ?)",
                    (
                        "part-1",
                        "credential-test",
                        "AIza1234567890abcdef",
                        json.dumps(
                            {
                                "type": "tool",
                                "tool": "ya29.1234567890",
                            }
                        ),
                    ),
                ),
            ],
        )
        serialized = json.dumps(reporter.generate_report(path))
        for value in (
            "ghp_1234567890abcdef",
            "xoxb-1234567890abcdef",
            "AKIA1234567890ABCD",
            "sk_live_1234567890",
            "rk_test_1234567890",
            "glpat-1234567890",
            "AIza1234567890abcdef",
            "ya29.1234567890",
        ):
            self.assertNotIn(value, serialized)

    def test_attempt_number_counts_only_attempts_after_the_first(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, attempt INTEGER, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("attempt-one", self.BASE_TIME_MS, self.BASE_TIME_MS + 1_000),
                ),
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("attempt-two", self.BASE_TIME_MS + 2_000, self.BASE_TIME_MS + 3_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?, ?)",
                    (
                        "message-one",
                        "attempt-one",
                        1,
                        json.dumps({"role": "assistant", "model": "model-a"}),
                    ),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?, ?)",
                    (
                        "message-two",
                        "attempt-two",
                        2,
                        json.dumps({"role": "assistant", "model": "model-a"}),
                    ),
                ),
            ],
        )
        sessions = reporter.generate_report(path)["sessions"]
        by_start = {session["start"]: session["retry_fallback"] for session in sessions}
        self.assertEqual(
            by_start["2023-11-14T22:13:20.000Z"],
            {"retry_count": 0, "retry_detected": False, "fallback_detected": False},
        )
        self.assertEqual(
            by_start["2023-11-14T22:13:22.000Z"],
            {"retry_count": 1, "retry_detected": True, "fallback_detected": False},
        )

    def test_extreme_timestamps_warn_and_return_partial_output(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("extreme", self.BASE_TIME_MS, self.BASE_TIME_MS + 1_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "m",
                        "extreme",
                        json.dumps(
                            {
                                "role": "assistant",
                                "time": {"start": 1e308, "end": 1e308},
                            }
                        ),
                    ),
                ),
            ],
        )
        report = reporter.generate_report(path)
        self.assertEqual(len(report["sessions"]), 1)
        self.assertIsNone(report["sessions"][0]["timing"]["model_duration_ms_approx"])
        self.assertTrue(any("outside the supported date range" in warning for warning in report["warnings"]))

    def test_malformed_json_is_a_warning_with_partial_output(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("s", self.BASE_TIME_MS, self.BASE_TIME_MS + 1_000),
                ),
                ("INSERT INTO message VALUES (?, ?, ?)", ("m", "s", "{not-json")),
            ],
        )
        report = reporter.generate_report(path)
        self.assertEqual(len(report["sessions"]), 1)
        self.assertTrue(any("malformed JSON" in warning for warning in report["warnings"]))
        self.assertIsNone(report["sessions"][0]["tokens"]["input"])

    def test_missing_tables_and_columns_are_warnings(self) -> None:
        path = self._database("CREATE TABLE session (id TEXT);", [("INSERT INTO session VALUES (?)", ("s",))])
        report = reporter.generate_report(path)
        self.assertTrue(report["sessions"][0]["session_id"].startswith("sha256:"))
        self.assertTrue(any("missing" in warning or "not found" in warning for warning in report["warnings"]))
        self.assertTrue(report["sessions"][0]["unknowns"])

    def test_sensitive_fields_are_not_emitted(self) -> None:
        path = self._database(
            """
            CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);
            CREATE TABLE message (id TEXT, session_id TEXT, data TEXT);
            CREATE TABLE part (id TEXT, session_id TEXT, data TEXT);
            """,
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("s", self.BASE_TIME_MS, self.BASE_TIME_MS + 1_000),
                ),
                (
                    "INSERT INTO message VALUES (?, ?, ?)",
                    (
                        "m",
                        "s",
                        json.dumps(
                            {
                                "role": "assistant",
                                "prompt": "SECRET_RAW_PROMPT",
                                "source": "SECRET_SOURCE_CODE",
                                "agent": "API_KEY_SHOULD_NOT_APPEAR",
                                "tokens": {"input": 1},
                            }
                        ),
                    ),
                ),
                (
                    "INSERT INTO part VALUES (?, ?, ?)",
                    (
                        "p",
                        "s",
                        json.dumps(
                            {
                                "type": "tool",
                                "tool": "safe_tool",
                                "state": {"input": "SECRET_RAW_ARGUMENT", "output": "SECRET_RAW_OUTPUT"},
                            }
                        ),
                    ),
                ),
            ],
        )
        serialized = json.dumps(reporter.generate_report(path))
        for secret in ("SECRET_RAW_PROMPT", "SECRET_SOURCE_CODE", "SECRET_RAW_ARGUMENT", "SECRET_RAW_OUTPUT"):
            self.assertNotIn(secret, serialized)

    def test_cli_json_output_shape(self) -> None:
        path = self._database(
            "CREATE TABLE session (id TEXT, time_created INTEGER, time_updated INTEGER);",
            [
                (
                    "INSERT INTO session VALUES (?, ?, ?)",
                    ("s", self.BASE_TIME_MS, self.BASE_TIME_MS + 1_000),
                )
            ],
        )
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--db", str(path), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        self.assertIsInstance(payload["sessions"], list)
        self.assertIsInstance(payload["aggregate"], dict)
        self.assertIsInstance(payload["warnings"], list)
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
