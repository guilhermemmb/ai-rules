import copy
import unittest
from pathlib import Path

try:
    from scripts.review_pipeline_contract import (
        compute_verdict,
        deduplicate_findings,
        load_registry,
        normalize_policy,
        resolve_concurrency,
        validate_lane_result,
        validate_packet,
    )
except ModuleNotFoundError:
    from review_pipeline_contract import (
        compute_verdict,
        deduplicate_findings,
        load_registry,
        normalize_policy,
        resolve_concurrency,
        validate_lane_result,
        validate_packet,
    )


ROOT = Path(__file__).parents[1]
REGISTRY_PATH = ROOT / ".rulesync/skills/review-pipeline/pipeline.json"


class ReviewPipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry(REGISTRY_PATH)

    def packet(self):
        return {
            "target": {"kind": "current-diff", "name": "task"},
            "scope": {"requested": "all", "target": "current-diff"},
            "diff": {"complete": True, "text": "diff --git a/app.py b/app.py\n+return value"},
            "changed_paths": ["app.py"],
            "diff_metadata": {"status": "complete", "source": "caller"},
            "implementer_report": {"status": "done"},
            "plan_context": {"task": 1},
            "guidelines": ["read-only review"],
            "policy": {"policy": {"kind": "auto"}},
            "review_run_id": "run-1",
            "packet_digest": "sha256:abc",
            "contract_version": 1,
        }

    def finding(self, severity="critical", **overrides):
        result = {
            "file": "app.py",
            "line": 12,
            "side": "changed",
            "hunk": "@@ -11,1 +12,1 @@",
            "issue": "Unsafe value",
            "confidence": 90,
            "fix": "Validate the value before use.",
            "severity": severity,
            "source_lane": "reviewer-code",
        }
        result.update(overrides)
        return result

    def lane_result(self, **overrides):
        result = {
            "agent": "reviewer-code",
            "review_run_id": "run-1",
            "packet_digest": "sha256:abc",
            "contract_version": 1,
            "phase": "A",
            "summary": "The changed code was reviewed.",
            "critical": [],
            "important": [],
            "suggestions": [],
            "positive": [],
            "errors": [],
        }
        result.update(overrides)
        return result

    def expected_run(self, **overrides):
        result = {
            "review_run_id": "run-1",
            "packet_digest": "sha256:abc",
            "contract_version": 1,
            "lane": "reviewer-code",
            "phase": "A",
        }
        result.update(overrides)
        return result

    def test_registry_has_canonical_lanes_and_fields(self):
        self.assertEqual(self.registry["manager"], "orchestrator")
        self.assertEqual(self.registry["skill"], "review-pipeline")
        self.assertNotIn("coordinator", self.registry)
        self.assertEqual(len(self.registry["lanes"]), 10)
        self.assertEqual(self.registry["phases"]["B"], ["reviewer-simplifier"])
        self.assertEqual(self.registry["max_phase_a_concurrency"], 3)
        self.assertIn("packet_digest", self.registry["required_packet_fields"])

    def test_valid_policies_and_target_defaults(self):
        self.assertEqual(normalize_policy(None, "current diff", self.registry), {"policy": {"kind": "auto"}})
        self.assertEqual(normalize_policy(None, "task", self.registry), {"policy": {"kind": "auto"}})
        for target in ("branch", "entire branch", "pr"):
            self.assertEqual(normalize_policy(None, target, self.registry), {"policy": {"kind": "full"}})
        self.assertEqual(normalize_policy("all", "pr", self.registry), {"policy": {"kind": "full"}})
        self.assertEqual(
            normalize_policy({"policy": {"kind": "aspects", "values": ["security", "errors"]}}, "task", self.registry),
            {"policy": {"kind": "aspects", "values": ["security", "errors"]}},
        )

    def test_invalid_policies(self):
        invalid = [
            "everything",
            {},
            {"policy": "full"},
            {"policy": {"kind": "all"}},
            {"policy": {"kind": "full", "values": []}},
            {"policy": {"kind": "aspects", "values": []}},
            {"policy": {"kind": "aspects", "values": ["security", "security"]}},
            {"policy": {"kind": "aspects", "values": ["all"]}},
            {"policy": {"kind": "aspects", "values": ["unknown"]}},
        ]
        for request in invalid:
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    normalize_policy(request, "task", self.registry)

    def test_policy_concurrency_and_lane_membership_are_registry_driven(self):
        registry = copy.deepcopy(self.registry)
        registry["policy"]["target_defaults"]["task"] = "full"
        registry["aspect_ids"] = ["custom"]
        registry["max_phase_a_concurrency"] = 2
        registry["phases"]["A"] = ["custom-lane"]
        registry["lanes"][0]["id"] = "custom-lane"
        registry["lanes"][0]["phase"] = "A"
        registry["lanes"][0]["aspect"] = "custom"
        self.assertEqual(normalize_policy(None, "task", registry), {"policy": {"kind": "full"}})
        self.assertEqual(
            normalize_policy({"policy": {"kind": "aspects", "values": ["custom"]}}, "task", registry),
            {"policy": {"kind": "aspects", "values": ["custom"]}},
        )
        self.assertEqual(resolve_concurrency("99", registry), 2)
        result = self.lane_result(agent="custom-lane")
        report = validate_lane_result(
            result,
            ["app.py"],
            {
                "review_run_id": "run-1",
                "packet_digest": "sha256:abc",
                "contract_version": 1,
                "lane_id": "custom-lane",
                "phase": "A",
            },
            registry,
        )
        self.assertTrue(report["valid"])

    def test_concurrency_parsing(self):
        self.assertEqual([resolve_concurrency(value, self.registry) for value in (None, "", "oops", "0", "-1")], [3] * 5)
        self.assertEqual([resolve_concurrency(value, self.registry) for value in (" 1 ", "2", 3)], [1, 2, 3])
        self.assertEqual(resolve_concurrency("4", self.registry), 3)
        self.assertEqual(resolve_concurrency("2.0", self.registry), 3)

    def test_valid_and_incomplete_packets(self):
        self.assertEqual(validate_packet(self.packet(), self.registry), {"valid": True, "errors": []})
        for field in self.registry["required_packet_fields"]:
            packet = self.packet()
            del packet[field]
            with self.subTest(field=field):
                report = validate_packet(packet, self.registry)
                self.assertFalse(report["valid"])
                self.assertTrue(any(field in error for error in report["errors"]))

    def test_packet_rejects_incomplete_diff_and_policy(self):
        packet = self.packet()
        packet["diff"]["complete"] = False
        packet["policy"] = {"policy": {"kind": "full", "extra": True}}
        report = validate_packet(packet, self.registry)
        self.assertFalse(report["valid"])
        self.assertEqual(
            report["errors"],
            ["diff must be complete and contain content", "invalid policy: full policy must contain exactly kind"],
        )

    def test_packet_validation_uses_supplied_registry_policy(self):
        registry = copy.deepcopy(self.registry)
        registry["policy"]["target_aliases"]["custom-target"] = "task"
        packet = self.packet()
        packet["target"] = {"kind": "custom-target", "name": "task"}
        self.assertEqual(validate_packet(packet, registry), {"valid": True, "errors": []})

    def test_valid_lane_result_preserves_source_lane(self):
        result = self.lane_result(critical=[self.finding()])
        report = validate_lane_result(result, ["app.py"], self.expected_run())
        self.assertTrue(report["valid"])
        self.assertEqual(report["findings"][0]["source_lane"], "reviewer-code")

    def test_lane_correlation_mismatches_and_late_result(self):
        for expected, result in (
            (self.expected_run(review_run_id="other"), self.lane_result()),
            (self.expected_run(lane="reviewer-test"), self.lane_result()),
            (self.expected_run(phase="B"), self.lane_result()),
            (self.expected_run(finalized=True), self.lane_result()),
        ):
            with self.subTest(expected=expected):
                report = validate_lane_result(result, ["app.py"], expected)
                self.assertFalse(report["valid"])

    def test_lane_rejects_packet_digest_and_contract_version_mismatches(self):
        for result in (
            self.lane_result(packet_digest="sha256:other"),
            self.lane_result(contract_version=2),
        ):
            report = validate_lane_result(result, ["app.py"], self.expected_run())
            self.assertFalse(report["valid"])
        self.assertIn(
            "packet_digest does not match expected run",
            validate_lane_result(self.lane_result(packet_digest="sha256:other"), ["app.py"], self.expected_run())["errors"],
        )
        self.assertIn(
            "contract_version does not match expected run",
            validate_lane_result(self.lane_result(contract_version=2), ["app.py"], self.expected_run())["errors"],
        )

    def test_lane_rejects_unknown_or_malformed_results(self):
        result = self.lane_result(agent="reviewer-unknown", critical={})
        report = validate_lane_result(result, ["app.py"], self.expected_run())
        self.assertFalse(report["valid"])
        self.assertIn("unknown lane agent", report["errors"])
        self.assertIn("lane field must be an array: critical", report["errors"])

    def test_lane_rejects_patch_anchor_without_changed_side_or_hunk(self):
        for missing in ("side", "hunk"):
            finding = self.finding()
            del finding[missing]
            report = validate_lane_result(self.lane_result(critical=[finding]), ["app.py"], self.expected_run())
            with self.subTest(missing=missing):
                self.assertFalse(report["valid"])
                self.assertIn("critical[0]: finding requires changed-side and hunk evidence", report["errors"])

    def test_lane_rejects_changed_path_confidence_and_remediation(self):
        findings = (
            self.finding(file="other.py"),
            self.finding(confidence=101),
            self.finding(fix=""),
        )
        for finding in findings:
            report = validate_lane_result(self.lane_result(critical=[finding]), ["app.py"], self.expected_run())
            self.assertFalse(report["valid"])

    def test_deduplicate_findings_keeps_highest_confidence_and_sources(self):
        low = self.finding(confidence=60, issue="Unsafe   VALUE", source_lane="reviewer-code")
        high = self.finding(confidence=95, issue=" unsafe value ", source_lane="reviewer-security")
        result = deduplicate_findings([low, high])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], 95)
        self.assertEqual(result[0]["source_lanes"], ["reviewer-code", "reviewer-security"])

    def test_deduplication_separates_severity_and_location(self):
        findings = [self.finding("critical"), self.finding("important"), self.finding("critical", line=13)]
        self.assertEqual(len(deduplicate_findings(findings)), 3)

    def test_verdict_precedence_and_every_state(self):
        self.assertEqual(compute_verdict("degraded", [self.finding("critical")]), "inconclusive")
        self.assertEqual(compute_verdict("healthy", [self.finding("critical")]), "blocked")
        self.assertEqual(compute_verdict("healthy", [self.finding("important")]), "changes-requested")
        self.assertEqual(compute_verdict("healthy", [self.finding("suggestions")]), "approved-with-suggestions")
        self.assertEqual(compute_verdict("healthy", []), "approved")
        self.assertEqual(compute_verdict("healthy", [self.finding("important"), self.finding("critical")]), "blocked")


if __name__ == "__main__":
    unittest.main()
