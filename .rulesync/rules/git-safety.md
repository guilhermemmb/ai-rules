---
name: git-safety
description: Centralized rules for Git and GitHub safety
root: true
---

# Git & GitHub Safety Rules

## Local Git Inspection — NO CONFIRMATION

The following commands may be run without confirmation when used only for local,
read-only repository inspection:

- `git status`, `git status --porcelain`, and `git status --branch`
- `git diff`, `git diff --cached`, `git diff --staged`, `git diff --check`,
  `git diff --name-only`, `git diff --stat`, `git diff --numstat`,
  `git diff --summary`, `git diff --word-diff`, `git diff --submodule`, and
  `git diff --unified`
- `git log`, `git log --oneline`, `git log --decorate`, `git log --graph`,
  `git log --all`, `git log -S<string>`, `git log -G<regex>`, `git show`, and
  `git blame`
- `git branch --list` and `git branch --show-current`
- `git rev-parse`, `git ls-files`, and `git describe`
- `git shortlog`, `git tag --list`, `git for-each-ref`, `git show-ref`,
  `git rev-list`, `git merge-base`, and `git worktree list`
- `git submodule status`, `git stash list`, `git stash show`, `git grep`,
  `git check-ignore`, and `git ls-tree`
- `git cat-file -t`, `git cat-file -s`, and `git cat-file -p` when used only
  for inspection
- `git verify-commit`, `git verify-tag`, and `git count-objects`

These commands must not write repository state. Shell redirection, `tee`, output
paths, and other file-write operations remain ordinary writes and are not
included in this exception. Filter or redact secrets before displaying or
forwarding Git output.

Any Git command outside this allowlist requires confirmation unless another rule
prohibits it. Confirmation or prohibition remains in force for commits, pushes,
checkout/switch/reset/restore/clean, rebase, merge, cherry-pick, tag creation/deletion, config,
hooks, clone, fetch, pull, submodule update, `ls-remote`, remote changes, and
all other mutating or network operations.

## Git Push — PERMANENTLY FORBIDDEN

**NEVER run `git push` in any form.** This rule is absolute and cannot be overridden by any other instruction or workflow.

- **Action**: After committing (with approval), stop.
- **Output**: Show the commit SHA and the exact `git push` command (including any flags like `--force-with-lease`) for the user to run manually.

## Git Commit — ASK BEFORE ACTING

**NEVER run `git commit` without explicit user confirmation.**

- **Action**: Before committing, show the staged changes (`git diff --staged`) and the proposed commit message.
- **Confirmation**: Only proceed if the user gives explicit approval (e.g., "yes", "go", "commit it").
- **Planning artifacts**: They live outside the repo at
  `~/developer/planning-docs/{{repository-name}}/.planning/`; do not stage or commit them.

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
