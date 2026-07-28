# Global Instructions

## Machine Configuration

- Always use zsh. Before running any command, source `~/.zshrc` first so the
  environment matches the interactive terminal.
- RTK is active via plugin and rewrites commands transparently — `git status`
  automatically becomes `rtk git status`. No manual prefixing needed.

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

## Branch Naming

- Always use `guilhermebomfim/` as the prefix (e.g.
  `guilhermebomfim/feature-name`), never `guilhermemmb/`

## GitHub API — Confirm Before Acting

**NEVER** run any `gh` CLI command that writes, mutates, or modifies state
without explicit user confirmation.

**Requires confirmation:** `gh pr create/merge/close/edit/comment/review` ·
`gh issue create/close/edit/comment` · `gh run rerun/cancel/delete` ·
`gh workflow run/enable/disable` · `gh release create/delete/edit` ·
`gh repo create/delete/edit/fork` · `gh api -X POST/PUT/PATCH/DELETE`

**NEVER run (no confirmation possible):** `gh run rerun` or any command that
triggers GitHub workflow runs.

**Allowed without confirmation:** `gh pr list/view/diff/checks` ·
`gh issue list/view` · `gh run list/view` · `gh workflow list/view` · `gh api`
(GET only) · `gh auth token/status`

## Git Push Safety

- **Never use `git push --force`** — use `git push --force-with-lease` only when
  explicitly instructed after a rebase/amend
- Never force-push to `main`/`master` under any circumstances
- Before executing ANY git command that writes to or alters the remote, always
  stop and ask for explicit confirmation. Show the exact command, explain what
  it does, then ask "Confirm?". Only proceed after explicit yes/go/confirm.
- Read-only git ops (status, log, diff, fetch) — no confirmation needed.

## PR Workflow

When asked to "create PR", "open PR", "update PR", "draft PR", or similar:

1. **Title**: conventional commit format — `type(scope): description`,
   lowercase, no trailing period, ≤100 chars. Drop scope if unclear.
2. **Description**: use `.github/PULL_REQUEST_TEMPLATE.md` if present. Include
   before/after metrics table when applicable.
   - Default structure if no template: Overview, Test Plan, Metrics/Context
   - Keep lean: Overview + test plan only. NO deep implementation details,
     line-by-line explanations, or architecture discussions.
3. **Write to file** (never paste full description into chat):
   - `.context/pr/<branch-name>.md` if `.context/` exists, otherwise
     `/tmp/pr-<branch-name>.md`
   - Format: first line `# <title>`, blank line, then body
4. **Show only** in chat: file path, one-line summary, exact `gh` command to
   run.
5. **Default to `--draft`** unless user says "ready for review".
6. **Always add label `claude:review`** to every PR (draft or not).
7. **Always ask for confirmation** before running any `gh pr create` or
   `gh pr edit` command.
8. **Reuse same file** when updating — overwrite it.

## Workflow

**Simple / straightforward tasks** — implement directly. Write a short inline
plan (numbered steps), then execute without waiting for approval.

**Non-trivial tasks** (new features, multi-area changes, unclear root cause) —
follow the **Spec Driven Development (SDD) workflow** defined below. Do NOT
create an ad-hoc inline plan; load the skill and generate the proper artifacts
instead.

## Spec Driven Development (SDD) Default Workflow — OpenSpec

**This is the default for all non-trivial work. Run it automatically — no user
command needed.**

**Skip SDD and implement directly only when:**

- User signals: "trivial", "quick fix", "minor", "just do it", "no SDD", "skip
  spec", "skip planning", or any clear synonym
- The change is a single-line / cosmetic / config-value edit with no design
  decision
- Explicit hotfix or incident response

**OpenSpec location — NEVER inside the repo:**

All OpenSpec artifacts live exclusively at
`~/developer/.ai-work/openspec/<repo>/`
where `<repo>` is the basename of the repo being worked on.
**Never create or write an `openspec/` folder inside the working repo.** The
repo must stay clean; the spec chain of thought lives outside it.

**For everything else, follow this workflow automatically:**

1. **Init** — derive `<repo>` from the current repo's directory basename. Check
   if a store already exists:
   ```bash
   openspec store list --json
   ```
   If no store with id `<repo>` exists, create one at the external path:
   ```bash
   openspec store setup <repo> --path ~/developer/.ai-work/openspec/<repo> --no-init-git
   ```
   This registers the external directory as the openspec home for this repo.
   **Never run `openspec init` inside the working repo.**

2. **Propose** — load skill `openspec-propose` and tell it to use
   `--store <repo>`. All artifacts (proposal.md, specs/, design.md, tasks.md)
   are written to the registered store path, not the repo. Show the user the
   artifacts and pause for approval before implementing.

3. **Apply** — load skill `openspec-apply-change` with `--store <repo>`. Work
   through tasks.md using the normal delegation model: @fixer for code changes,
   @designer for UI/UX, @oracle for architecture decisions.

4. **Archive** — load skill `openspec-archive-change`. When invoking, explicitly
   tell the skill: "Archive using store `<repo>`. Pass `--store <repo>` on every
   openspec command. The archive must land at
`~/developer/.ai-work/openspec/<repo>/changes/archive/`, never
inside the working repo."

**Optional explore step:** If the task is ambiguous or codebase impact is
unclear, load `openspec-explore` before proposing. This is
thinking/clarification time — skip it for well-scoped requests.

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
- **Never use mcp-server-browser tools directly** — dispatch to **Navigator**
- **Never use cortex MCP directly** — dispatch to **Sage** or **Librarian**
- **Never use Linear MCP directly** — dispatch to **Librarian**
- **For Gorgias/internal Notion links or docs** — delegate to **Sage** (extracts page ID, uses Cortex)
- **For public Notion pages** — delegate to **Librarian**

## Codebase Memory MCP

**MANDATORY: use codebase-memory-mcp graph tools FIRST — before reading files or
making code changes.**

Call `list_projects` first when project name unknown. Use the `display_name` or
exact `name` returned.

**Tools:**

- `search_graph` — primary entry point. Full-text BM25 query, name_pattern
  regex, semantic_query vector. Narrow with label, file_pattern, min_degree.
  Paginate via offset/limit.
- `search_code` — graph-augmented text search ranked by importance
- `get_architecture` — high-level overview: packages, services, routes,
  hotspots, clusters
- `trace_path` — follow CALLS/DATA_FLOW/CROSS_SERVICE edges; impact analysis,
  call chains
- `get_code_snippet` — read source for a symbol (find qualified_name via
  search_graph first)
- `query_graph` — Cypher for multi-hop patterns, aggregations, complexity
  queries
- `get_graph_schema` / `detect_changes` — inspect schema; map git diff to
  affected symbols
- `index_repository` — build/update graph
  (full/moderate/fast/cross-repo-intelligence)
- `list_projects` / `index_status` / `delete_project` — manage indexed projects
- `ingest_traces` / `manage_adr` — validate call edges; read/write Architecture
  Decision Records

**Workflow:** list_projects → get_architecture → search_graph (find symbol) →
get_code_snippet or trace_path → query_graph for complex patterns. Fall back to
Read/grep only for exact line-level edits or unindexed symbols.

**Project name** = absolute root_path slugified:
`/Users/foo/developer/gorgias-chat` → `Users-foo-developer-gorgias-chat`

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
