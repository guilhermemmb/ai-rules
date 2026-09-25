---
description: Multi-focus code review — PR, branch, staged, or unstaged changes
argument-hint: "pr <url> [focus] | branch|staged|unstaged [focus]"
---
Load the `review-pipeline` skill and run a review with scope `${1:-branch}`.

Scope details:
- `pr <url> [focus]` — Review a pull request. Argument 2 is the PR URL, never a focus filter. Use `gh pr diff` and `gh pr view` against that URL.
  Example: `/review pr https://github.com/owner/repo/pull/42`
- `branch [focus]` — Review current branch changes against the resolved repository comparison base.
  Example: `/review branch`
- `staged [focus]` — Review only staged changes (git diff --cached).
  Example: `/review staged`
- `unstaged [focus]` — Review tracked unstaged changes (git diff); disclose that untracked files are excluded.
  Example: `/review unstaged`

For `pr`, the optional focus filter is argument 3; for other scopes it is argument 2. Match focus ID or label by case-insensitive substring. Examples: `/review branch security` and `/review pr https://github.com/owner/repo/pull/42 security`. An explicit filter replaces automatic focus selection; label the verdict “filtered scope only” and list excluded focuses. Missing PR URLs, unknown scopes, extra arguments, or unmatched filters are input errors, not passing reviews.

Follow the review-pipeline flow exactly: gather pinned evidence → select focuses → preflight the predefined reviewer → prepare evidence under its agent-owned safety policy → dispatch once → validate identities and coverage → aggregate report. Every focus inherits the same predefined reviewer model, thinking and permissions; never substitute models. Output the final Markdown report inline; evidence artifacts may use the canonical external planning reports directory. Stop after the report and await explicit user approval before any fixes.
