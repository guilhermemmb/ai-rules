# Global Instructions

## Machine Configuration

- Always use zsh. Before running any command, source `~/.zshrc` first so the
  environment matches the interactive terminal.
- RTK plugin transparently optimizes ordinary commands. See `code-exploration` rule for discovery routing.

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
- `GITHUB_PERSONAL_ACCESS_TOKEN` — populated via `gh auth token`
- `NPM_TOKEN` — GitHub npm registry auth

## PATH Components (in order)

- `$VOLTA_HOME/bin`, `~/.local/bin`, `~/.antigravity/antigravity/bin`,
  `$PNPM_HOME` (`~/Library/pnpm`), `~/developer/gorgi`, Orbstack shell init
  (`~/.orbstack/shell/init.zsh`)

## npm Registry

- `@gorgias` scope: registry at `https://npm.pkg.github.com/` (auth via
  `$NPM_TOKEN`)

## SSH Config

- Includes `~/.ssh/conductor_config` and `~/.orbstack/ssh/config`

## Shell Functions & Aliases

- `dbproxy` — interactive fzf selector for cloud-sql-proxy connections
- Project: `g:gorgias`, `g:chat`, `g:incoming`, `g:account-manager`,
  `g:workflows`, `g:help-center`, `g:helpdesk`, `g:ai-agent`
- Proxy: `g:proxy`, `g:proxy-chat`, `g:proxy-helpdesk`
- PR: `g:pr`, `g:pr-checkout`, `g:pr-rebase`
- Git: `gpo`, `gpof`, `gpfo` (force-with-lease), `grsoh`, `grbm`, `gro`, `gcp`,
  `grbi`, `grbc`

## Development Environment

- **Never run any git command on your own — always ask and confirm first.**
  Covers commit, push, checkout, rebase, merge.
- If a test or lint command fails to run, ask which command to use and where the
  root folder is, then remember it.
- When tests fail, show only the errors — filter the console output, don't dump
  it raw.
- Always run lint to fix files before finishing an implementation.

## Package Manager & Monorepo Paths

- Always check which package manager the project uses first — start with `pnpm`.
- For workspace/monorepo commands, path is relative to the package, not the repo
  root. e.g. `pnpm --filter @gorgias-chat/client test:unit src/foo/Bar.spec.tsx`

## Commit Messages

- Conventional commits: `type(scope): description`. Types: `feat`, `fix`,
  `docs`, `style`, `refactor`, `test`, `chore`.
- Title ≤ 100 chars, lowercase, present tense, no trailing period. Drop scope if
  unclear.
- Never add `Co-Authored-By:` lines or any AI attribution.
- Summarize the changed files, don't explain every detail. Reference issue
  numbers when applicable.

## Dispatch Rules

- **Never use Sentry/GCP-Logging/Rootly tools directly** — dispatch to
  **Detective**
- **Never run `pup` directly for Datadog queries** — dispatch to **Detective**
- **Never invoke the `agent-browser` CLI or use `chrome-devtools-mcp` directly** —
  dispatch browser work to **Navigator**. Navigator is the exception and runs
  `agent-browser` through Bash.
- **Never use cortex MCP directly** — dispatch to **Sage** or **Librarian**
- **Never use Linear MCP directly** — dispatch to **Librarian**
- **For Gorgias/internal Notion links or docs** — delegate to **Sage** (extracts page ID, uses Cortex)
- **For public Notion pages** — delegate to **Librarian**

## Security Scan (on-demand)

Before any `git commit`, `git push`, or `git rebase` (also on branch switch, or
when working on a branch with an open PR), scan the diff. If ANY red flag found:
**STOP**, show `file:line`, ask before proceeding.

**What to look for:**

1. **Mock/test data & hardcoded payloads** — mock API responses, dummy arrays,
   `res.send([{…}])`, `return [{…}]`
2. **Debug return values** — `return true/false` that ignores logic, bypassed
   feature flags, short-circuit returns
3. **Cleanup leftovers** — 3+ unused imports, commented-out code blocks, dead
   code paths
4. **Sensitive hardcoded values** — API keys, tokens, passwords, credentials,
   internal URLs, DB strings, hardcoded user ids, `console.log` with sensitive
   data
5. **Development artifacts** — debug flags set to `true`, hardcoded env values

**Search keywords in the diff:** `return true/false` · `res.send([` ·
`res.json([/{` · `mock/dummy/fake/hardcode` · `TODO/FIXME/HACK/XXX` ·
`console.log/warn/debugger` · large object/array literals (>3 lines) · `// `
(commented code) · imports from `/mocks/`, `/fixtures/`, `/test-utils/`

**Proceed without confirmation only if:**

- Changes are in test files (`*.test.*`, `*.spec.*`, `__tests__/`,
  `*.stories.*`)
- Mock data is in designated dirs (`__mocks__/`, `fixtures/`, `test-data/`)
- File is clearly a config/constant file for sample data
- Unused imports are part of a refactor a linter will clean up
- User has explicitly confirmed the code is intentional

**Dev-mode pattern for intentional mock/debug code:**

```typescript
// ❌ BAD — naked mock response
export const getThings = async (req, res) => {
  res.json([{ id: 1, name: "Sample" }]);
};
// ✅ GOOD — gated behind dev-mode check
export const getThings = async (req, res) => {
  if (isDevMode) {
    return res.json([{ id: 1, name: "Sample" }]);
  }
  res.json(await db.things.findAll());
};
```

## General

- Temporary-file cleanup period: 7 days.
