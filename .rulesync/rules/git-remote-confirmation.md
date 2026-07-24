---
name: git-remote-confirmation
description: Confirm before any git/gh command that writes to or alters the remote
metadata:
  type: rule
---

# Git Remote & GitHub — Confirm Before Acting

Before executing ANY command that writes to or alters the remote, **always stop and ask the user for explicit confirmation first**. This includes:

- `git push` (including `--force-with-lease`)
- `git push --delete` (deleting remote branches)
- `gh pr create`, `gh pr edit`, `gh pr merge`, `gh pr close`
- `gh issue create`, `gh issue edit`, `gh issue close`
- `gh release create`, `gh release edit`, `gh release delete`
- `gh api` with POST / PUT / PATCH / DELETE
- Any other command that mutates state on the GitHub remote

## Confirmation format

Show the user:
1. The exact command(s) you intend to run
2. What it will do (branch name, PR number, etc.)
3. Ask: "Confirm?"

Only proceed after the user explicitly says yes / go / confirm.

## Read-only operations — no confirmation needed

These can run freely without asking:
- `git status`, `git log`, `git diff`, `git fetch`
- `gh pr list`, `gh pr view`, `gh pr checks`, `gh pr diff`
- `gh run list`, `gh run view`
- `gh issue list`, `gh issue view`
- Any other read-only `gh` or `git` command
