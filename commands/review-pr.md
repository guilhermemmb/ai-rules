---
description: "Review a pull request using pr-review-toolkit agents"
targets: ["claudecode"]
---

# Review PR

Dispatch a comprehensive PR review using the `pr-review-toolkit` specialized
agents.

Optional aspect filter: $ARGUMENTS (comments | tests | errors | types | code |
simplify | all) If not provided, default to `all`.

Run `/pr-review-toolkit:review-pr $ARGUMENTS`

Do NOT run `gh pr comment` to post results — the GitHub API read-only rule in
overview.md blocks all write operations. Print findings to terminal only.
