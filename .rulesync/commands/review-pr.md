---
name: review-pr
description: AI rules/agent definition for review-pr.md
targets: ["opencode"]
---

# Review PR

This repository's command dispatches exactly one `@reviewer-coordinator` with a complete review packet. The orchestrator must not preload the coordinator skill, select or directly dispatch `reviewer-*` lanes, run Phase B, aggregate findings, or compute the verdict. Do not call `functions.skill` or silently fall back to a partial direct-lane review.

Review target and mode: current diff/task defaults to `auto`; entire branch, branch, and PR default to `full`. An explicit `auto`, `full`, or aspect list overrides the target default. Aspect list values: comments | tests | errors | types | security | performance | data-integrity | code | simplify | accessibility | all.

The coordinator selects from exactly 10 reviewer-* lanes — reviewer-code, reviewer-test, reviewer-errors, reviewer-types, reviewer-security, reviewer-performance, reviewer-data-integrity, reviewer-accessibility, reviewer-comments, and reviewer-simplifier. `full` runs all nine Phase A concern lanes, then reviewer-simplifier exactly once as sequential Phase B when the normalized diff contains a non-empty executable/source/config diff. `auto` selects applicable lanes from the changed diff. Concern lanes run in background batches up to the resolved `REVIEWER_MAX_PARALLEL` limit (1–3). Failed, timed-out, unavailable, malformed, or incomplete lane results are recorded in `errors` and make Review Health Degraded/inconclusive. The command returns a structured report with Review Health, Critical / Important / Suggestions / Strengths / Recommended Action. This is a runtime setting only; do not add it as an OpenCode config key.

Do NOT run `gh pr comment` or any other `gh` write/mutation command to post results — GitHub API access is read-only in this repository. Print findings to terminal only.
