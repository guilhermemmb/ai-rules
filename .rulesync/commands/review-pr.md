---
name: review-pr
description: AI rules/agent definition for review-pr.md
targets: ["opencode"]
---

# Review PR

At this review boundary, the `orchestrator` is the review manager and loads the on-demand
`review-pipeline` skill and validates the `pipeline.json` registry at
`__AI_RULES_REVIEW_PIPELINE_REGISTRY_PATH__`.
It builds one redacted immutable packet, selects focus IDs from the catalog,
and dispatches a fresh `reviewer` invocation for every selected focus. Each
invocation gets a unique `review_invocation_id`; run at most three concurrently,
wait for the batch, and reconcile exact returned session IDs. Never revive a
session for a new focus, use aliases, or introduce a phase dependency.

Keep packet redaction, untrusted-evidence boundaries, complete-diff and hunk
evidence, strict JSON/result validation, reviewer/focus/invocation correlation,
health-first inconclusive behavior, read-only evidence, and validation evidence.
Every finding cites a changed file, positive line, side, hunk, confidence,
issue, and fix. The final response is one inline Markdown report with Review
Health, verdict, findings, strengths, recommended action, and validation
evidence.
