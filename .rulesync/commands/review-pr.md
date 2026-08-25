---
name: review-pr
description: AI rules/agent definition for review-pr.md
targets: ["claudecode"]
---

# Review PR

Dispatch @reviewer to review the current PR or branch diff.

Optional aspect filter: $ARGUMENTS (comments | tests | errors | types | security | performance | data-integrity | code | simplify | accessibility | all). If not provided, default to `all`.

The @reviewer agent selects from 10 reviewer-\* lanes — reviewer-code (always), reviewer-test, reviewer-errors, reviewer-types, reviewer-security, reviewer-performance, reviewer-data-integrity, reviewer-accessibility, reviewer-comments, and reviewer-simplifier — based on the changed diff. Concern lanes are independent and may run in background batches up to the resolved `REVIEWER_MAX_PARALLEL` limit. After all Phase A concern batches complete, reviewer-simplifier runs exactly once as sequential Phase B only when selected/applicable—when the normalized diff contains a non-empty executable/source/config diff and the aspect filter permits it—and receives the consolidated Phase A findings. Failed, timed-out, unavailable, malformed, or incomplete lane results are recorded in `errors` and make Review Health Degraded/inconclusive. The command returns a structured report with Review Health, Critical / Important / Suggestions / Strengths / Recommended Action. This is a runtime setting only; do not add it as an OpenCode config key.

Do NOT run `gh pr comment` to post results — the GitHub API read-only rule in overview.md blocks all write operations. Print findings to terminal only.
