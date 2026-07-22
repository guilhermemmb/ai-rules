# Global Instructions

## Branch Naming

- Always use `guilhermebomfim/` as the prefix (e.g. `guilhermebomfim/feature-name`), never `guilhermemmb/`

## GitHub API — Read-Only Mode

**NEVER** run any `gh` CLI command or GitHub API call that writes, mutates, or modifies state. This is NOT overridable.

**Blocked:** `gh pr create/merge/close/edit/comment/review` · `gh issue create/close/edit/comment` · `gh run rerun/cancel/delete` · `gh workflow run/enable/disable` · `gh release create/delete/edit` · `gh repo create/delete/edit/fork` · `gh api -X POST/PUT/PATCH/DELETE`

**Allowed:** `gh pr list/view/diff/checks` · `gh issue list/view` · `gh run list/view` · `gh workflow list/view` · `gh api` (GET only) · `gh auth token/status`

## Git Push Safety

- **Never use `git push --force`** — use `git push --force-with-lease` only when explicitly instructed after a rebase/amend
- Never force-push to `main`/`master` under any circumstances

## Forbidden Commands

- **NEVER run `gh run rerun`** or any command that triggers GitHub workflow runs
- The `collect` commands in gh-actions-metrics are read-only only

## PR Workflow

When asked to "create PR", "open PR", "update PR", "draft PR", or similar:

1. **Title**: conventional commit format — `type(scope): description`, lowercase, no trailing period, ≤100 chars. Drop scope if unclear.

2. **Description**: use `.github/PULL_REQUEST_TEMPLATE.md` if present. Include before/after metrics table when applicable (lint counts, bundle size, test scores).

3. **Write to file** (never paste full description into chat):
   - `.context/pr/<branch-name>.md` if `.context/` exists
   - Otherwise `/tmp/pr-<branch-name>.md`
   - Format: first line `# <title>`, blank line, then body

4. **Show only** in chat: file path, one-line summary, and the exact `gh` command to run.

5. **Default to `--draft`** unless user says "ready for review".

6. **Reuse same file** when updating — overwrite it.

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

## Communication Style

- Default to caveman lite: no filler, no hedging. Keep articles + full sentences.
  Switch with /caveman lite | /caveman full | /caveman ultra.
- Compress memory files with /caveman:compress <filepath> — overwrites file, backs up as FILE.original.md.

# Claude Code Configuration

## Status Line Setup

Enable the caveman mode status line badge in Claude Code settings:

```json
{
  "statusLine": {
    "type": "command",
    "command": "context-mode statusline"
  }
}
```

Add to `.claude/settings.json` in each project root, or to `~/.claude/settings.json` for global activation.

Displays active caveman mode level (`[CAVEMAN]`, `[CAVEMAN:LITE]`, `[CAVEMAN:ULTRA]`) in the editor's status bar.

# Custom Rules (always applied)

## Machine Configuration
- Always use zsh. Before running any command, source my `~/.zshrc` first so the environment
  matches my interactive terminal.

## Workflow
- Create a plan first. Show me the plan in digestible chunks and wait for my "go" before
  applying it.

## Superpowers Persistence
- Persist ALL Superpowers artifacts (brainstorming notes, plans, design docs, skill outputs)
  under `/Users/guilhermebomfim/developer/gorgias-power-project/<repo>/superpowers/`, where
  `<repo>` is the repo currently being worked on.
- This applies EVEN when the working directory is a repo elsewhere — never write these artifacts
  into the repo itself; always centralize them under the path above.
- READ from there too: before brainstorming, planning, or resuming work on a repo, check
  `.../gorgias-power-project/<repo>/superpowers/` for existing artifacts and use them as context.
- Compose both sources: combine the repo itself (code, docs, in-repo artifacts) WITH the
  centralized artifacts at that path — read them together, not one or the other.

## Development Environment
- **Never run any git command on your own — always ask and confirm first.** This is the single
  source of truth for git behavior and covers commit, push, checkout, rebase, and merge.
- If a test or lint command fails to run, ask me which command to use and where the root folder
  is, then remember it.
- When tests fail, show me only the errors — filter the console output, don't dump it raw.
- Always run lint to fix files before finishing an implementation.

## Package Manager & Monorepo Paths
- Always check which package manager the project uses first — start with `pnpm`.
- For workspace/monorepo commands, the path is relative to the package you're working on, not the
  repo root. e.g. `pnpm --filter @gorgias-chat/client test:unit src/foo/Bar.spec.tsx`.

## Commit Messages
- Conventional commits: `type(scope): description`. Types: `feat`, `fix`, `docs`, `style`,
  `refactor`, `test`, `chore`.
- Title ≤ 100 chars, lowercase, present tense ("add feature" not "added feature"), no trailing
  period. If the scope is unclear or there are multiple, drop it: `type: description`.
- Never add `Co-Authored-By:` lines or any AI attribution.
- Keep it simple: summarize the changed files, don't explain every detail. Reference issue
  numbers when applicable (#123). Detailed context goes in the body if needed.

**Examples**
- Good: `feat(chat): add message retry functionality`
- Good: `fix(bundle): reduce bundle size by removing unused deps`
- Bad: `Added new feature` · `Fixed bug.` · `Update`

## General
- Temporary-file cleanup period: 15 days.

## Commit / Push Safety
- Before any `git commit`, `git push`, or `git rebase` (and on branch switch, or when working on
  a branch with an open PR), read and apply security-scan rules.

# Pull Request Workflow

## Git Command Safety

**NEVER** run any git command without asking first. This applies to:
- `git commit`
- `git push` / `git push --force-with-lease`
- `git checkout` / `git switch`
- `git rebase`
- `git merge`

Always confirm the command and context with the user before executing.

## PR Creation & Updates

### General Rules
- **Always ask for confirmation** before running any `gh pr create` or `gh pr edit` command
- **Always use `--draft`** by default (unless user explicitly says "ready for review")
- **Always add label `claude:review`** to every PR (draft or not)

### Title Format
- Use conventional commit format: `type(scope): description`
- `type`: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- `scope`: Optional; drop if unclear or multiple areas affected
- `description`: Lowercase, present tense, ≤100 chars total, no trailing period
- Examples:
  - `feat(auth): add jwt token refresh`
  - `fix: resolve null pointer in data processor`

### Description
- Save to file, **never paste inline**:
  - `.context/pr/<branch-name>.md` if `.context/` exists
  - `/tmp/pr-<branch-name>.md` otherwise
- Format: First line `# <title>`, blank line, then body
- Check for `.github/PULL_REQUEST_TEMPLATE.md` in the target repo
  - If found: reference and follow its structure
  - If not found: use default structure (Overview, Test Plan, Metrics/Context)
- **Keep descriptions lean**: Overview + test plan only
  - NO deep implementation details
  - NO line-by-line code explanations
  - NO architecture discussions (save for commit messages or comments)

### When Updating a PR
- Reuse the same description file from step 1
- Overwrite it with new content
- Provide the exact `gh pr edit` command

## Command Format

Always give the user a copyable command block. Example:

```sh
# Create draft PR with label
gh pr create --base main --draft \
  --title "$(head -1 /tmp/pr-feature-name.md | sed 's/^# //')" \
  --body-file <(tail -n +3 /tmp/pr-feature-name.md) \
  --label claude:review
```

```sh
# Update existing PR
gh pr edit 42 \
  --title "$(head -1 /tmp/pr-feature-name.md | sed 's/^# //')" \
  --body-file <(tail -n +3 /tmp/pr-feature-name.md)
```

# Commit / Push Safety Scan

On-demand checklist. Read and apply this before any `git commit`, `git push`, or `git rebase`
(also on branch switch, and when working on a branch with an open PR). It is intentionally
kept out of always-loaded context — load it only when one of those triggers fires.

If ANY red flag is found: **STOP**, show the exact `file:line` with context, explain what looks
wrong, and ask before proceeding.

## What to look for

1. **Mock / test data & hardcoded payloads** — mock API responses, dummy data arrays/objects,
   sample payloads, early returns with hardcoded data (`res.send([{…}])`, `return [{…}]`).
2. **Debug return values** — hardcoded `return true` / `return false`, bypassed feature flags or
   conditionals, short-circuit returns, functions that ignore their own logic.
3. **Cleanup leftovers** — 3+ unused imports in one file (strong signal of an unfinished debug
   session), commented-out code blocks, unused vars/functions, dead code paths.
4. **Sensitive hardcoded values** — API keys, tokens, passwords, credentials, internal URLs,
   DB connection strings, hardcoded user ids/emails, debug flags set to `true`, `console.log`
   with sensitive data.
5. **Development artifacts** — temporary debug code, dev-only flags, hardcoded env values.

## Search keywords in the diff

`return true` / `return false` (esp. when they ignore the logic above) · `res.send([` ·
`res.json([` / `res.json({` · `mock` / `dummy` / `fake` / `hardcode` · `TODO` / `FIXME` /
`HACK` / `XXX` · `console.log` / `console.warn` / `debugger` · large object/array literals
(>3 lines) in returns/responses · lines starting with `// ` (commented code) · imports from
`/mocks/`, `/fixtures/`, `/test-utils/` in production code.

## Process

1. `git diff --staged` (or the relevant commit range) to review changes.
2. Scan each changed file against the categories and keywords above.
3. On any hit: STOP, report `file:line`, ask for confirmation.

## Proceed without confirmation only if

- Changes are in test files (`*.test.*`, `*.spec.*`, `__tests__/`, `*.stories.*`).
- Mock data lives in designated dirs (`__mocks__/`, `fixtures/`, `test-data/`).
- The file is clearly a config/constant file meant to hold sample data.
- Unused imports are part of a refactor a linter will clean up.
- The user has explicitly confirmed the code is intentional.

## Dev-mode pattern for intentional mock/debug code

Never commit raw mock code. Always gate it behind a development-mode env check so it can't run
in production. Use the project's own dev-mode signal (check the project's CLAUDE.md / `.rulesync`
for the exact env var — e.g. a backend `NODE_ENV` check vs. a frontend build-env check).

```typescript
// ❌ BAD — naked mock response
export const getThings = async (req, res) => {
    res.json([{ id: 1, name: 'Sample' }])
}

// ✅ GOOD — gated behind the project's dev-mode check
export const getThings = async (req, res) => {
    if (isDevMode) {
        return res.json([{ id: 1, name: 'Sample' }])
    }
    res.json(await db.things.findAll())
}
```

## Git Configuration

- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com)
- SSH signing key: `~/.ssh/id_ed25519.pub`
- Commit signing: GPG format SSH, always signed
- Pull strategy: rebase (`pull.rebase = true`)
- Allowed signers: `~/.ssh/allowed_signers`

## Environment Variables (defined in ~/.zshrc)

- `GOPATH=~/go`
- `VOLTA_HOME=$HOME/.volta` (Node version manager, used for pnpm, node)
- `EDITOR=vim`
- `GORGIAS_ROOT=/Users/guilhermebomfim/developer`
- `BAO_ADDR` — Vault address
- `HOMEASSISTANT_URL` + `HOMEASSISTANT_TOKEN` — Home Assistant API
- `GITHUB_PERSONAL_ACCESS_TOKEN` — populated via `gh auth token`
- `NPM_TOKEN` — GitHub npm registry auth

## PATH Components (in order)

- `$VOLTA_HOME/bin`
- `~/.local/bin`
- `~/.antigravity/antigravity/bin`
- `$PNPM_HOME` (`~/Library/pnpm`)
- `~/developer/gorgi`
- `/Applications/Visual Studio Code.app/Contents/Resources/app/bin`
- Orbstack shell init (`~/.orbstack/shell/init.zsh`)

## npm Registry

- `@gorgias` scope: registry at `https://npm.pkg.github.com/` (auth via `$NPM_TOKEN`)

## SSH Config

- Includes `~/.ssh/conductor_config` and `~/.orbstack/ssh/config`

## Shell Functions

- `dbproxy` — interactive fzf selector for cloud-sql-proxy connections
- `unify-ai-config` — symlinks AI config across tools (via `~/developer/dotfiles/unify-ai-config.mjs`)

## Project Aliases (defined in ~/.zshrc)

- `g:gorgias`, `g:chat`, `g:incoming`, `g:account-manager`, `g:workflows`, `g:help-center`, `g:helpdesk`, `g:ai-agent` — cd shortcuts to `~/developer/<project>`
- `g:proxy`, `g:proxy-chat`, `g:proxy-helpdesk` — local dev proxy launchers
- `g:pr`, `g:pr-checkout`, `g:pr-rebase` — PR tool shortcuts
- `g:ngrok`, `g:ngrok-tmux` — ngrok launchers
- `g:push-staging` — force-push staging branch

## Git Aliases (defined in ~/.zshrc)

- `gpo` — git push origin
- `gpof` — git push origin --force
- `gpfo` — git push --force-with-lease origin
- `grsoh` — git reset --soft HEAD^1
- `grbm` — fetch + rebase on origin/main with stash
- `gro` — fetch + rebase on origin/main
- `gcp` — git cherry-pick
- `grbi` — git rebase -i
- `grbc` — git rebase --continue
