---
name: git-safety
description: Centralized rules for Git and GitHub safety
---

# Git & GitHub Safety Rules

## Git Push — PERMANENTLY FORBIDDEN

**NEVER run `git push` in any form.** This rule is absolute and cannot be overridden by any other instruction or workflow.

- **Action**: After committing (with approval), stop.
- **Output**: Show the commit SHA and the exact `git push` command (including any flags like `--force-with-lease`) for the user to run manually.

## Git Commit — ASK BEFORE ACTING

**NEVER run `git commit` without explicit user confirmation.**

- **Action**: Before committing, show the staged changes (`git diff --staged`) and the proposed commit message.
- **Confirmation**: Only proceed if the user gives explicit approval (e.g., "yes", "go", "commit it").

## GitHub PRs — GENERATE ONLY

**NEVER run `gh pr create` or `gh pr edit` to mutate state.**

- **Action**: Generate the PR title and description.
- **Template**: Always check for and follow the project's PR template (e.g., `.github/PULL_REQUEST_TEMPLATE.md`).
- **File**: Write the generated content to `.context/pr/<branch-name>.md` or `/tmp/pr-<branch-name>.md`. Format: First line `# <title>`, then the body.
- **Output**: Show the file path and the exact `gh pr create --draft --label claude:review ...` or `gh pr edit ...` command for the user to run manually.

## GitHub API — READ-ONLY MODE

**NEVER run any `gh` command or API call that writes, mutates, or modifies state.**

- **Blocked**: `gh pr merge/close/review`, `gh issue create/close/edit`, `gh run rerun/cancel`, `gh workflow run/enable/disable`, `gh release create/delete`, etc.
- **Allowed**: `gh pr list/view/diff`, `gh issue list/view`, `gh run list/view`, `gh auth token/status`.
