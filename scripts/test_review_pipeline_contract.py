import unittest
from pathlib import Path

try:
    from scripts.review_pipeline_contract import (
        compute_verdict,
        deduplicate_findings,
        load_registry,
        normalize_policy,
        resolve_concurrency,
        validate_packet,
        validate_reviewer_result,
    )
except ModuleNotFoundError:
    from review_pipeline_contract import (
        compute_verdict,
        deduplicate_findings,
        load_registry,
        normalize_policy,
        resolve_concurrency,
        validate_packet,
        validate_reviewer_result,
    )

ROOT = Path(__file__).parents[1]
REGISTRY_PATH = ROOT / ".rulesync/skills/review-pipeline/pipeline.json"


class ReviewPipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry(REGISTRY_PATH)

    def packet(self):
        return {
            "target": {"kind": "current-diff", "name": "task"}, "scope": {"requested": "all", "target": "current-diff"},
            "diff": {"complete": True, "text": "diff --git a/app.py b/app.py\n+return value"}, "changed_paths": ["app.py"],
            "diff_metadata": {"status": "complete", "source": "caller"}, "implementer_report": {"status": "done"},
            "plan_context": {"task": 1}, "guidelines": ["read-only review"], "policy": {"policy": {"kind": "auto"}},
            "review_run_id": "run-1", "review_invocation_id": "inv-1", "packet_digest": "sha256:abc", "contract_version": 2,
        }

    def finding(self, **overrides):
        result = {"file": "app.py", "line": 12, "side": "changed", "hunk": "@@ -11,1 +12,1 @@", "issue": "Unsafe value", "confidence": 90, "fix": "Validate the value before use."}
        result.update(overrides)
        return result

    def result(self, **overrides):
        result = {"reviewer": "reviewer", "review_run_id": "run-1", "review_invocation_id": "inv-1", "packet_digest": "sha256:abc", "contract_version": 2, "focus": "code", "summary": "The changed code was reviewed.", "critical": [], "important": [], "suggestions": [], "positive": [], "errors": []}
        result.update(overrides)
        return result

    def detailed_report(self, **overrides):
        report = {
            "scope": "Reviewed the changed app.py lines for the code focus.",
            "approach": "Compared the complete diff with authoritative native evidence.",
            "assessment": "The changed code has one actionable concern.",
            "checks_performed": ["Reviewed changed control flow."],
            "limitations": ["No runtime execution was supplied."],
            "unknowns": ["Production traffic shape is unknown."],
            "findings": [{
                "severity": "important", "file": "app.py", "line": 12,
                "side": "changed", "hunk": "@@ -11,1 +12,1 @@",
                "narrative": "The changed value is used without validation.",
                "evidence_basis": "The changed line is the first unchecked use.",
                "reasoning": "The unchecked use creates a path for invalid input.",
                "impact": "Unexpected input can reach the downstream operation.",
                "remediation": "Validate the value before the downstream operation.",
            }],
        }
        report.update(overrides)
        return report

    def expected(self, **overrides):
        result = {"review_run_id": "run-1", "review_invocation_id": "inv-1", "packet_digest": "sha256:abc", "contract_version": 2, "reviewer": "reviewer", "focus": "code"}
        result.update(overrides)
        return result

    def test_registry_has_v2_focus_catalog(self):
        self.assertEqual(self.registry["contract_version"], 2)
        self.assertEqual(self.registry["max_concurrency"], 3)
        self.assertEqual(self.registry["focus_ids"], ["code", "tests", "errors", "types", "security", "performance", "data-integrity", "accessibility", "comments", "simplify"])
        self.assertEqual({focus["target"] for focus in self.registry["focuses"]}, {"reviewer"})
        self.assertNotIn("lanes", self.registry)
        self.assertNotIn("phases", self.registry)
        self.assertTrue(all("model_profile" not in key for key in self.registry))
        self.assertIn("review_invocation_id", self.registry["required_packet_fields"])
        self.assertIn("source_focus", self.registry["finding_fields"])
        self.assertIn("source_invocation_id", self.registry["finding_fields"])

    def test_policies_and_concurrency(self):
        self.assertEqual(normalize_policy(None, "current diff", self.registry), {"policy": {"kind": "auto"}})
        self.assertEqual(normalize_policy(None, "pr", self.registry), {"policy": {"kind": "full"}})
        self.assertEqual(normalize_policy("all", "pr", self.registry), {"policy": {"kind": "full"}})
        self.assertEqual(normalize_policy({"policy": {"kind": "aspects", "values": ["security", "errors"]}}, "task", self.registry), {"policy": {"kind": "aspects", "values": ["security", "errors"]}})
        with self.assertRaises(ValueError):
            normalize_policy({"policy": {"kind": "aspects", "values": ["unknown"]}}, "task", self.registry)
        self.assertEqual([resolve_concurrency(value, self.registry) for value in (None, "", "oops", "0", "-1")], [3] * 5)
        self.assertEqual([resolve_concurrency(value, self.registry) for value in (" 1 ", "2", 3, "99")], [1, 2, 3, 3])

    def test_packet_contract_requires_invocation(self):
        self.assertEqual(validate_packet(self.packet(), self.registry), {"valid": True, "errors": []})
        packet = self.packet()
        del packet["review_invocation_id"]
        self.assertFalse(validate_packet(packet, self.registry)["valid"])
        packet = self.packet()
        packet["diff"]["complete"] = False
        self.assertIn("diff must be complete and contain content", validate_packet(packet, self.registry)["errors"])

    def test_result_correlation_focus_and_evidence(self):
        report = validate_reviewer_result(self.result(critical=[self.finding()]), ["app.py"], self.expected(), self.registry)
        self.assertTrue(report["valid"])
        self.assertEqual(report["findings"][0]["source_focus"], "code")
        self.assertEqual(report["findings"][0]["source_invocation_id"], "inv-1")
        for expected, result in ((self.expected(review_invocation_id="other"), self.result()), (self.expected(focus="security"), self.result()), (self.expected(finalized=True), self.result())):
            self.assertFalse(validate_reviewer_result(result, ["app.py"], expected, self.registry)["valid"])

    def test_detailed_report_is_preserved_and_validated_when_present(self):
        report = self.detailed_report()
        validation = validate_reviewer_result(self.result(report=report), ["app.py"], self.expected(), self.registry)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["report"], report)
        invalid = self.detailed_report(findings=[{"severity": "important", "file": "other.py", "line": 12, "side": "changed", "hunk": "@@", "narrative": "Unsupported.", "evidence_basis": "Unsupported.", "reasoning": "Unsupported.", "impact": "Unsupported.", "remediation": "Unsupported."}])
        self.assertFalse(validate_reviewer_result(self.result(report=invalid), ["app.py"], self.expected(), self.registry)["valid"])

    def test_legacy_result_without_detailed_report_remains_valid(self):
        self.assertTrue(validate_reviewer_result(self.result(), ["app.py"], self.expected(), self.registry)["valid"])

    def test_result_rejects_unknown_reviewer_and_bad_finding(self):
        report = validate_reviewer_result(self.result(reviewer="other-reviewer", critical=[self.finding()]), ["app.py"], self.expected(), self.registry)
        self.assertFalse(report["valid"])
        report = validate_reviewer_result(self.result(critical=[self.finding(line=0)]), ["app.py"], self.expected(), self.registry)
        self.assertFalse(report["valid"])

    def test_deduplication_keeps_highest_confidence_and_sources(self):
        low = self.finding(confidence=60, issue="Unsafe   VALUE", source_focus="code", source_invocation_id="inv-1")
        high = self.finding(confidence=95, issue=" unsafe value ", source_focus="security", source_invocation_id="inv-2")
        result = deduplicate_findings([{**low, "severity": "critical"}, {**high, "severity": "critical"}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], 95)
        self.assertEqual(result[0]["source_focuses"], ["code", "security"])

    def test_verdict_health_first(self):
        finding = {"severity": "critical"}
        self.assertEqual(compute_verdict("degraded", [finding]), "inconclusive")
        self.assertEqual(compute_verdict("healthy", [finding]), "blocked")
        self.assertEqual(compute_verdict("healthy", []), "approved")


if __name__ == "__main__":
    unittest.main()
