---
description: Multi-focus code review — PR, branch, staged, or unstaged changes
argument-hint: "<pr|branch|staged|unstaged> [detail]"
---
Load the `review-pipeline` skill and run a review with scope `${1:-branch}`.

Scope details:
- `pr <url>` — Review a pull request. Use `gh pr diff` and `gh pr view` against the provided PR URL.
  Example: `/review pr https://github.com/owner/repo/pull/42`
- `branch` — Review all changes on the current branch vs origin/main.
  Example: `/review branch`
- `staged` — Review only staged changes (git diff --cached).
  Example: `/review staged`
- `unstaged` — Review only unstaged changes (git diff).
  Example: `/review unstaged`

If a second argument is provided, use it as a filter — only dispatch reviewers whose focus ID or label matches (case-insensitive substring match). Example: `/review branch security` reviews only the security focus.

Follow the review-pipeline flow exactly: gather evidence → select focuses → redact packet → dispatch reviewer subagents → reconcile → aggregate report. Output the final Markdown report inline without writing files.
