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

- Local, read-only Git inspection does not require confirmation for `git status`,
  `git status --porcelain`, `git status --branch`, `git diff`,
  `git diff --cached`, `git diff --staged`, `git diff --check`,
  `git diff --name-only`, `git diff --stat`, `git diff --numstat`,
  `git diff --summary`, `git diff --word-diff`, `git diff --submodule`,
  `git diff --unified`, `git log`, `git log --oneline`, `git log --decorate`,
  `git log --graph`, `git log --all`, `git log -S<string>`,
  `git log -G<regex>`, `git show`, `git blame`, `git branch --list`,
  `git branch --show-current`, `git rev-parse`, `git ls-files`, `git describe`,
  `git shortlog`, `git tag --list`, `git for-each-ref`, `git show-ref`,
  `git rev-list`, `git merge-base`, `git worktree list`, `git submodule status`,
  `git stash list`, `git stash show`, `git grep`, `git check-ignore`,
  `git ls-tree`, `git cat-file -t`, `git cat-file -s`, `git cat-file -p` when
  used only for inspection, `git verify-commit`, `git verify-tag`, and
  `git count-objects`.
- Use those commands only for local inspection; they must not write repository
  state. Shell redirection, `tee`, output paths, and other file-write operations
  remain ordinary writes and are not smuggled into this exception. Filter or
  redact secrets before displaying or forwarding Git output.
- Ask for confirmation for Git commands outside that allowlist unless a safety
  rule prohibits them. Mutating and network operations—including commit, push,
  checkout, switch, reset, restore, clean, rebase, merge, cherry-pick, tag
  creation/deletion,
  config, hooks, clone, fetch, pull, submodule update, `ls-remote`, remote
  changes, and other Git writes or network access—remain subject to the central
  Git safety rules.
- If a test or lint command fails to run, ask which command to use and where the
  root folder is, then remember it.
- When tests fail, show only the errors — filter the console output, don't dump
  it raw.
- Lint is check-only by default. Run lint with autofix only when the handoff
  explicitly includes a `Lint Autofix` directive, and limit autofix to the files
  listed in that directive.

## Package Manager & Monorepo Paths

- Always check which package manager the project uses first — start with `pnpm`.
- For workspace/monorepo commands, path is relative to the package, not the repo
  root. e.g. `pnpm --filter @gorgias-chat/client test:unit src/foo/Bar.spec.tsx`

## Code Exploration

- Serena provides supplementary semantic navigation and impact analysis. Native
  RTK/OpenCode tools remain authoritative for exact local evidence, files,
  shell, tests, configuration, documentation, and edits.

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

## OpenCode Multi-Fixer Scheduler

For approved L/XL plans, OpenCode's orchestrator is the only implementation
scheduler. It may run at most **3** independent `@fixer` children in one batch;
this is a scheduler contract, not an unsupported top-level OpenCode setting.

Before dispatching, normalize every task's complete write set: every path it
may create, modify, delete, or generate, including reports, planning files,
lockfiles, and generated output. Require exact `Files`, `Interfaces/Constraints`,
dependencies/producers/consumers, validation, and stop conditions. Missing,
ambiguous, overlapping, shared-resource, generated-output, lockfile, or
explicitly ordered work is serial. A consumer waits for its producer and a
dependent waits for implementation **and review**.

For each eligible batch:

1. Select only ready tasks with pairwise disjoint, complete write sets.
2. Dispatch one fresh `@fixer` per task with `background=true`, recording the
   exact returned child session ID and job ID. Never infer IDs from aliases,
   titles, ordering, or task descriptions.
3. Wait for every dispatched task in the same batch. Reconcile each terminal
   result by its exact returned session ID with `task_result`; a partial wait or
   malformed result is not completion.
4. Reconcile changed paths against each child's declared `Files` allowlist.
   The fixer may create, modify, or delete only those paths. The allowlist is a
   cooperative prompt contract because OpenCode does not provide a dynamic
   per-task path ACL; runtime smoke must detect violations and fail closed.
5. At every review boundary, load and use the on-demand `review-pipeline` skill. The orchestrator is the review manager and owns packet validation, policy normalization, lazy focus selection, bounded fresh dispatch of the single `reviewer` agent, exact-session reconciliation, aggregation, health-first verdict computation, and the final Markdown report. Never preload the skill into every orchestrator session. Dispatch only the exact focus IDs declared by the canonical `.rulesync/skills/review-pipeline/pipeline.json` registry.
6. Build a complete packet with target descriptor, scope, complete diff,
    changed paths, diff metadata, implementer's report, task/plan context,
    project guidelines, normalized policy, unique `review_run_id`, stable
    `packet_digest`, and the registry `contract_version`. Redact secrets and
    untrusted instructions, enforce the skill's input size limits and escaping,
    and pass the same packet plus focus instruction and a unique `review_invocation_id` to every child.
7. Launch selected focuses in canonical registry order in background batches no larger than the registry cap (maximum 3), wait for each batch, and reconcile every result by its exact returned session ID. Every focus gets a fresh `reviewer` invocation; never revive, alias, directly fall back, or add a phase dependency. Preserve valid results while recording late, timed-out, unavailable, malformed, missing, duplicate, mismatched, or cross-invocation results as health failures.
8. Require each reviewer result to echo `review_run_id`, `review_invocation_id`, `packet_digest`, `contract_version`, and `focus`. Validate strict JSON, changed-file, numeric-line, changed-side/hunk, non-empty issue/remediation, and 0–100 confidence requirements before retaining findings. Attribute findings with `source_focus` and `source_invocation_id`. Separate coverage health from finding content; health failures take precedence over content verdicts. Guard finalization and emit the required inconclusive fallback report with raw valid findings/errors if rendering fails.
9. Do not release any dependent until the review pipeline passes, or an
    explicit `@oracle` adjudication resolves it. Be honest about parent
    write-isolation: read-only child permissions and prompt claims are not
    filesystem immutability without authoritative recorded tool evidence.

`NEEDS_CONTEXT`, `BLOCKED`, timeout or failure, failed, missing, or malformed implementer
or review results hold all dependents and must be surfaced in the scheduler
report. Unrelated ready tasks may continue in another safe batch. Never create
an extra fixer to work around an ownership conflict; stop the affected lane
and re-sequence it.

## Background Validation Event Relay

Every background fixer must emit validation events as execution happens. Before
each typecheck, unit-test, integration-test, build, or lint command, the child
must emit `Validation started — <category>: <exact command>`; after it ends, the
child must emit exactly one terminal event: passed with exit status and observed
duration when available, failed with exit status and filtered errors only,
skipped with an explicit reason, or unavailable with the exact inability/error.

Relay each child start event to the user immediately when received, followed by
the matching terminal event immediately when received. Do not wait for, or
replace the event stream with, only the child's final summary. Preserve the
ordered start/terminal event history by child and category in the scheduler and
handoff reports. Do not synthesize a passed event when an event is missing; mark
the check not-run or unavailable with the exact observed reason. A background
child's final report must retain the same per-category command, start event,
terminal event, status, exit status when observed, and reason/error when not
passed. Relay lint using the existing check-only/autofix policy and filtered
error rules.

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
