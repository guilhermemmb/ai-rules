---
description: Multi-focus code review — PR, branch, staged, or unstaged changes
argument-hint: "<pr|branch|staged|unstaged> [detail]"
---
Load the `review-pipeline` skill and run the sole review workflow with scope `${1:-branch}`. Do not invoke any other review skill or independent reviewer for this scope.

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

Follow the review-pipeline flow exactly: gather evidence → select focuses → redact packet → dispatch the pipeline's focus reviewers → reconcile → aggregate one final report → return it to the orchestrator and pause. Do not run a parallel or independent review outside this pipeline. Do not fix code, dispatch implementation work, commit, or continue past the report without explicit user approval. Output every finding with its issue, impact, location, and proposed fix in the final Markdown report inline without writing files.
