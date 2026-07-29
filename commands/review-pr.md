---
description: "Review a pull request using the @reviewer subagent"
targets: ["claudecode"]
---

# Review PR

Dispatch @reviewer to review the current PR or branch diff.

Optional aspect filter: $ARGUMENTS (comments | tests | errors | types | code | simplify | accessibility | all). If not provided, default to `all`.

The @reviewer agent spawns 7 reviewer-* specialists in parallel, aggregates findings, and returns a structured report (Critical / Important / Suggestions / Strengths / Recommended Action).

Do NOT run `gh pr comment` to post results — the GitHub API read-only rule in overview.md blocks all write operations. Print findings to terminal only.
