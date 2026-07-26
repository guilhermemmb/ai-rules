# Git Remote & GitHub — Confirm Before Acting

## gh CLI — blocked commands

**NEVER** run any `gh` CLI command or GitHub API call that writes, mutates, or modifies state without explicit user confirmation. This is NOT overridable.

**Requires confirmation before running:**
- `gh pr create`, `gh pr merge`, `gh pr close`, `gh pr edit`, `gh pr comment`, `gh pr review`
- `gh issue create`, `gh issue close`, `gh issue edit`, `gh issue comment`
- `gh run rerun`, `gh run cancel`, `gh run delete`
- `gh workflow run`, `gh workflow enable`, `gh workflow disable`
- `gh release create`, `gh release delete`, `gh release edit`
- `gh repo create`, `gh repo delete`, `gh repo edit`, `gh repo fork`
- `gh api` with `-X POST`, `-X PUT`, `-X PATCH`, `-X DELETE`

**NEVER run (no confirmation possible):**
- `gh run rerun` or any command that triggers GitHub workflow runs

**Allowed without confirmation:**
- `gh pr list`, `gh pr view`, `gh pr diff`, `gh pr checks`
- `gh issue list`, `gh issue view`
- `gh run list`, `gh run view`
- `gh workflow list`, `gh workflow view`
- `gh api` (GET only)
- `gh auth token`, `gh auth status`

## git — confirm before acting on remote

Before executing ANY git command that writes to or alters the remote, **always stop and ask the user for explicit confirmation first**. This includes:

- `git push` (including `--force-with-lease`)
- `git push --delete` (deleting remote branches)

## Confirmation format

Show the user:
1. The exact command(s) you intend to run
2. What it will do (branch name, PR number, etc.)
3. Ask: "Confirm?"

Only proceed after the user explicitly says yes / go / confirm.

## Read-only git operations — no confirmation needed

- `git status`, `git log`, `git diff`, `git fetch`
- Any other read-only `git` command

