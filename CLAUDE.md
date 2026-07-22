# Global Claude Instructions

## Branch Naming
- Always use `guilhermebomfim/` as the branch prefix (e.g. `guilhermebomfim/feature-name`), never `guilhermemmb/`

## GitHub API — Read-Only Mode

**NEVER** run any `gh` CLI command or GitHub API call that writes, mutates, or modifies state. This is NOT overridable, even if the user asks.

**Blocked:** `gh pr create/merge/close/edit/comment/review` · `gh issue create/close/edit/comment` · `gh run rerun/cancel/delete` · `gh workflow run/enable/disable` · `gh release create/delete/edit` · `gh repo create/delete/edit/fork` · `gh api -X POST/PUT/PATCH/DELETE`

**Allowed (read-only):** `gh pr list/view/diff/checks` · `gh issue list/view` · `gh run list/view` · `gh workflow list/view` · `gh api` (GET only) · `gh auth token/status`

## Git Push Safety

- **Never use `git push --force`** — use `git push --force-with-lease` only when explicitly instructed after a rebase/amend
- Never force-push to `main`/`master` under any circumstances

## Forbidden Commands
- **NEVER run `gh run rerun`** or any command that triggers/re-triggers GitHub workflow runs
- The `collect` commands in gh-actions-metrics are **read-only** — only collect metrics, never trigger actions

## PR Workflow

When asked to "create PR", "open PR", "update PR", "draft PR", or similar:

1. **Title**: `type(scope): description` — lowercase, no trailing period, ≤100 chars. Drop scope if unclear.
2. **Description**: use `.github/PULL_REQUEST_TEMPLATE.md` if present. Include before/after metrics when applicable.
3. **Save to file** (never paste full description in chat):
   - `.context/pr/<branch-name>.md` if `.context/` exists, otherwise `/tmp/pr-<branch-name>.md`
   - Format: first line `# <title>`, blank line, then body
4. **Show in chat only**: file path · one-line summary · exact `gh` command to run
5. **Default to `--draft`** unless user says "ready for review"
6. **Reuse same file** when updating an existing PR

**Commands to give the user:**
```sh
# Create draft PR
gh pr create --base <base> --draft \
  --title "$(head -1 <file> | sed 's/^# //')" \
  --body-file <(tail -n +3 <file>)

# Update existing PR
gh pr edit <number> \
  --title "$(head -1 <file> | sed 's/^# //')" \
  --body-file <(tail -n +3 <file>)
```

---

## Workflow

- Create a plan first. Show it in digestible chunks and wait for "go" before applying
- Always use **zsh**. Source `~/.zshrc` before running commands
- **Never run any git command without confirming first** — covers commit, push, checkout, rebase, merge
- When tests fail, show only the errors — filter console output, never dump it raw
- Always run lint before finishing an implementation
- Temporary file cleanup period: 15 days

## Superpowers Persistence

- Persist ALL Superpowers artifacts under `/Users/guilhermebomfim/developer/gorgias-power-project/<repo>/superpowers/`
- Never write artifacts into the repo itself — always centralize under the path above
- Before starting any task, check that path for existing artifacts and combine with repo context

## Package Manager & Monorepo

- Check package manager first — default to `pnpm`
- For monorepo commands, path is relative to the package, not repo root
  e.g. `pnpm --filter @gorgias-chat/client test:unit src/foo/Bar.spec.tsx`

## Commit Messages

- Format: `type(scope): description` · lowercase · present tense · ≤100 chars · no trailing period
- Types: `feat` `fix` `docs` `style` `refactor` `test` `chore`
- Drop scope if unclear; never add `Co-Authored-By:` lines

## Commit / Push Safety

Before any `git commit`, `git push`, or `git rebase` (and on branch switch, or when working on a branch with an open PR), load and apply the security-scan checklist:

**Scan for:** mock/hardcoded payloads · `return true`/`return false` bypassing logic · 3+ unused imports · commented-out code · API keys/secrets · debug artifacts · early returns skipping normal flow

On any hit: **STOP**, show `file:line` with context, ask before proceeding.

Skip confirmation only for: test files · designated mock dirs (`__mocks__/`, `fixtures/`) · user-confirmed intentional code.

**Dev-mode pattern** — never commit raw mock code; always gate:
```typescript
if (process.env.NODE_ENV === 'development') {
    return res.json([{ id: 1, name: 'Sample' }])
}
```

## Test Execution

- Redirect output: `<cmd> 2>&1 | tee /tmp/test-output.log`
- Show only errors from the log
- If no code changed since last run, read the log instead of re-running

---

## User Environment

### Git Configuration
- User: Guilherme Bomfim (guilherme.bomfim@gorgias.com)
- SSH signing key: `~/.ssh/id_ed25519.pub` — commits are always GPG-SSH signed
- Pull strategy: rebase (`pull.rebase = true`)

### Key Environment Variables
- `GORGIAS_ROOT=/Users/guilhermebomfim/developer`
- `GOPATH=~/go` · `VOLTA_HOME=$HOME/.volta` · `EDITOR=vim`
- `GITHUB_PERSONAL_ACCESS_TOKEN` — via `gh auth token`
- `BAO_ADDR` — Vault · `HOMEASSISTANT_URL` / `HOMEASSISTANT_TOKEN` — Home Assistant API
- `NPM_TOKEN` — GitHub npm registry (`@gorgias` scope → `https://npm.pkg.github.com/`)

### Project Aliases (`~/developer/`)
`g:chat` · `g:gorgias` · `g:incoming` · `g:account-manager` · `g:workflows` · `g:help-center` · `g:helpdesk` · `g:ai-agent` · `g:proxy` · `g:proxy-chat` · `g:proxy-helpdesk` · `g:pr` · `g:pr-checkout` · `g:pr-rebase`

### Git Aliases
- `gpfo` — `git push --force-with-lease origin`
- `grsoh` — `git reset --soft HEAD^1`
- `grbm` — fetch + stash + rebase origin/main + stash apply
- `gro` — fetch + rebase origin/main
- `grbi` / `grbc` — rebase interactive / continue
