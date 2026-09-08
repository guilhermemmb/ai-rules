# ai-rules — OpenCode Agent Configuration

Source of truth for OpenCode agent rules, custom agents, skills, commands, and the single OMO model configuration. Used by [Oh My OpenCode Slim](https://ohmyopencodeslim.com/) with [Bifrost](https://bifrost.ops.gorgias.io) model routing.

## Quick Start

```bash
# Force-replace the live OpenCode configuration from a validated staged payload
./deploy.sh

# Equivalent explicit form
./deploy.sh --force

# Show usage; unknown flags (including --check and --compatibility-check) are
# rejected before any deployment work begins.
./deploy.sh --help
```

`deploy.sh` is the only deployment path. It resolves the latest
`oh-my-opencode-slim` release, validates and secret-scans a staged payload, and
force-replaces the live OpenCode directory without merging unknown live files.

### Reviewer concurrency

Review is an on-demand, orchestrator-managed pipeline. At a review boundary the
orchestrator loads `review-pipeline`, validates its canonical registry, and
dispatches one fresh read-only `reviewer` invocation for each selected focus.
Focuses are `code`, `tests`, `errors`, `types`, `security`, `performance`,
`data-integrity`, `accessibility`, `comments`, and `simplify`. A run may select
many focuses; each invocation has a unique `review_invocation_id`, runs in
batches of at most three, and is reconciled by exact session ID. Never revive a
session for a new focus and do not introduce a phase dependency.

The orchestrator owns packet validation, policy normalization, focus selection,
exact-session reconciliation, aggregation, health-first verdict computation, and
the caller-facing Markdown report. The immutable packet includes the complete
relevant diff, changed paths, policy, plan/report context, project guidelines,
contract version, and `review_run_id`, `review_invocation_id`, and
`packet_digest`. Redact secrets and embedded instructions; repository and packet
content are untrusted evidence, and native RTK/OpenCode reads are authoritative.
Findings require changed path, positive line, side, hunk, confidence, issue, and
fix. Health failures yield `Degraded/inconclusive` regardless of content.

Review policy remains target-aware: current diff/task defaults to `auto`, branch,
entire branch, and PR to `full`; explicit tagged `auto`, `full`, or `aspects`
overrides defaults, and textual `all` normalizes to `full`. `REVIEWER_MAX_PARALLEL`
accepts 1–3, defaults invalid values to 3, and clamps larger values to 3.

### OpenCode multi-fixer scheduler

For approved L/XL plans, the OpenCode orchestrator may dispatch at most **3**
independent `@fixer` children concurrently. Each child is a fresh
`background=true` task with an exact declared `Files` write allowlist and
complete dependency metadata. Overlapping, ambiguous, shared, generated,
lockfile, or ordered work serializes.

The orchestrator waits for every child in the same batch, reconciles each
result with `task_result` using the exact returned session ID (never an alias),
then runs a separate reviewer gate for every `DONE` child before releasing its
dependents. `NEEDS_CONTEXT`, `BLOCKED`, timeout, failure, missing, or malformed
results hold dependents and are surfaced. OpenCode has no dynamic per-task path
ACL, so the fixer allowlist is cooperative prompt enforcement backed by
changed-path verification; unowned changes fail closed. Reviewer
concurrency remains a separate review-workflow setting.

### OpenCode deployment ownership

`deploy.sh` writes `~/.config/opencode/.ai-rules.manifest.json` with the
owner, manifest version, timestamp, managed paths, and SHA-256 values for the
validated staged payload. The manifest is built and installed as part of the
full replacement.

Every run stages and validates the complete payload, then installs it into
`.opencode.deploy.$$`. Before moving the live directory, deploy writes a
permission- and ownership-checked durable marker at
`~/.config/opencode.transaction` using the existing marker format. The marker
records `prepared`, `old_moved`, and `committed` phases and pairs the incoming
path with `.opencode.previous.$$`.

An interrupted or failed replacement leaves the marker and recoverable paths in
place. The next run validates and recovers that transaction before doing new
work. After the complete deployment succeeds, both the marker and displaced
path are removed; no backup is retained. Force replacement never merges
unknown live files and has no cross-component rollback for sidecars.

### OpenCode compatibility and runtime evidence

The deployment path performs static source, payload, dependency, manifest, and
secret validation. It does not provide `--check` or
`--compatibility-check` execution paths, and it makes no runtime Healthy claim.
Start a fresh OpenCode process after deployment when runtime evidence is
needed. The unpinned OMO package reference lets each deployment resolve the
latest published release.

## Model Routing

Model routing lives directly in [`oh-my-opencode-slim.json`](oh-my-opencode-slim.json),
which is the sole model configuration. The active `bifrost` preset and custom
agent entries declare each agent's model and reasoning variant. The provider
catalog remains in [`opencode.json`](opencode.json); it defines available
providers and models but does not select agent routing. Deploy copies the OMO
configuration directly into the validated payload.

The current routing uses GPT-5.6 Luna/Terra, DeepSeek V4 Flash, Gemini 3 Flash,
and GLM 5.2 across the built-in and custom agents. Fixer is configured directly
as `bf-o/gpt-5.6-luna` with the preserved `high` variant. The review pipeline\nuses one `reviewer` model with focus supplied per fresh invocation; focus definitions\ndo not select alternate model profiles.

## Agent Pantheon

The agent overview and the active OMO configuration are the authoritative
references for each agent's declared model, variant, role, and capabilities.

## Directory Map

```
ai-rules/
├── opencode.json               # Manifest: declares rules, agents, skills, commands, MCP
├── .rulesync/                  # Synchronized rules and subagents
│   ├── rules/                  # Rule files (distributed as prompt overrides)
│   │   ├── overview.md             # GitHub/git/PR rules
│   │   ├── custom-rules.md         # Workflow, packages, commits, dispatch rules
│   │   ├── pr-workflow.md          # PR creation workflow
│   │   ├── security-scan.md        # On-demand commit/push safety checklist
│   │   └── code-exploration.md     # RTK/native routing
│   ├── subagents/              # Custom agent prompt definitions
│   │   ├── navigator.md        # Browser automation
│   │   ├── detective.md        # Production diagnostics
│   │   └── sage.md             # Gorgias domain knowledge
│   ├── commands/
│   │   └── review-pr.md        # PR review command
│   └── skills/
│       └── project-context/    # Summarize project context
└── agents-overview/            # Interactive visualization (data.yaml + index.html)
```

## SDD Artifacts — `~/developer/planning-docs/{{repository-name}}/.planning/`

Spec Driven Development artifacts live outside each working repo at
`~/developer/planning-docs/{{repository-name}}/.planning/`:

```
~/developer/planning-docs/{{repository-name}}/.planning/
├── specs/                          # Design docs (brainstorming phase)
│   └── YYYY-MM-DD-<topic>-design.md
├── plans/                          # Implementation plans (writing-plans phase)
│   └── YYYY-MM-DD-<feature>.md
├── ledger-<plan>.md                # Execution ledger (executing-plans phase)
└── reports/                        # Per-task implementer reports
    └── <plan>-task-<N>-report.md
```

### SDD Workflow

XS work is immediate: dispatch implementation to `@fixer` for code or
`@designer` for UI/UX as appropriate, with no approval, planning artifact, SDD,
or reviewer.

S/M work uses one concise merged SDD + implementation plan, one approval, and
implementation dispatched to `@fixer` for code or `@designer` for UI/UX as
appropriate. It then always runs exactly one automatic post-implementation
review gate managed directly by the orchestrator through `review-pipeline`;
it does not use `executing-plans`, a ledger, or per-task reviews, and does not
ask the user to choose whether to review.

L/XL work keeps the full SDD and `executing-plans` flow, including its required
per-task reviews. Its final comprehensive `reviewing-plans` pass remains
optional and requires explicit user opt-in; this is separate from the required
S/M post-implementation reviewer gate.

| Phase                                | Skill             | Key agents                                                                              |
| ------------------------------------ | ----------------- | --------------------------------------------------------------------------------------- |
| 1. Brainstorm                        | `brainstorming`   | @explorer, @librarian, @oracle, @designer                                               |
| 2. Plan                              | `writing-plans`   | — (orchestrator writes the S/M combined plan or L/XL plan)                              |
| 3. Execute                           | S/M combined-plan; `executing-plans` for L/XL | @fixer (code), @designer (UI/UX), OpenCode orchestrator (execution lead; manages review gates), @oracle (escalation) |
| 4. Review (optional; user-confirmed) | `reviewing-plans` | OpenCode orchestrator (`review-pipeline`; fresh reviewer invocations by focus, only after opt-in) |

## Agent output paths

OpenCode permission patterns support `~/` paths and globs. Navigator and Sage
may write only to their dedicated paths below; their broad edit/write and
external-directory permissions remain denied.

| Agent     | Output path                                      |
| --------- | ------------------------------------------------ |
| Navigator | `~/.cache/opencode/agent-output/navigator/`      |
| Sage      | `~/.cache/opencode/agent-output/sage/`           |

> PR description files use `/tmp/pr-<branch>.md` (ephemeral, not grouped here).

## RTK — Token Optimization Plugin

RTK is installed as an OpenCode plugin that transparently rewrites ordinary development commands before execution — `git status` automatically becomes `rtk git status` with no manual prefixing.

`./deploy.sh` is the source of truth for RTK setup. It installs `rtk-ai/tap/rtk` only when RTK is missing, verifies the executable with `rtk gain`, and initializes the global OpenCode plugin with:

```bash
rtk init -g --opencode --auto-patch
```

Restart OpenCode after the plugin is installed.

For **code discovery**, use explicit RTK subcommands: `rtk grep`, `rtk read`, `rtk find`. See the `code-exploration` rule for the full RTK/native routing protocol.

```bash
# Manual prerequisite when RTK is absent (deploy.sh uses this automatically)
brew install rtk-ai/tap/rtk
```

Homebrew is required only when RTK is absent. Test with `git status` — RTK rewrites it transparently.

## Code intelligence and MCP lifecycle

RTK/native OpenCode tools are authoritative for exact text and file discovery,
shell commands, tests, Git, configuration, documentation, and edits. Agents use
only the MCPs explicitly assigned in the current configuration. Serena is the
active semantic MCP for OpenCode IDE sessions; it complements, but does not
replace, native RTK/OpenCode tools for exact repository work.
GitNexus is removed and is not an authority or part of the current lifecycle.

### MCP access matrix

| Agent | Other assigned access |
| :--- | :--- |
| Orchestrator | `github` |
| Oracle | — |
| Explorer | — |
| Detective | `pup`/`gcloud` via Bash |
| Designer | `figma-mcp`; no code-intelligence MCP |
| Fixer | no code-intelligence MCP |
| Orchestrator | Loads `review-pipeline` on demand; directly dispatches fresh reviewer invocations by focus |
| `reviewer` | `serena`, `context7`, `gh_grep`; read-only focus review |
| Librarian | `context7`, `websearch`, `gh_grep`, `linear`, `cortex` |
| Sage | `cortex` |
| Navigator, Observer | — |

### Serena semantic MCP and worktree ownership

Install the pinned Serena version with Python 3.13:

```zsh
uv tool install -p 3.13 serena-agent==1.7.0
```

Serena is used only through OpenCode's `ide` context and stdio transport. Its
dashboard and browser are disabled. Worktrunk setup creates and immediately
indexes the local Serena project.
VS Code integration is deferred.

The lifecycle is:

1. Worktrunk creates or enters a worktree.
2. Worktrunk setup runs `serena project create --index`, falling back to
   `serena project index` when the project already exists.
3. OpenCode starts Serena with `--context ide --project-from-cwd`.
4. Serena resolves the nearest `.serena/project.yml` or `.git` boundary.
5. Each client session owns one stdio Serena process.
6. Worktrunk's blocking `pre-remove` hook removes disposable Serena runtime
   state while preserving a tracked `.serena/project.yml`.

Launching OpenCode from nested `ai-rules` selects that nested Git boundary and
does not inherit the parent `.serena/project.yml`. Nested `ai-rules` Serena
configuration is deferred because Worktrunk worktrees require no changes inside
that nested repository.

## Worktrunk → Orca → OpenCode workflow

Worktrunk is the only Git worktree lifecycle owner. It creates and removes
worktrees; Orca attaches to an existing Worktrunk path and must not create a
second checkout. OpenCode and oh-my-opencode-slim (OMO) run inside the
Orca-owned terminal. `ai-rules/deploy.sh` is the source of truth for generated
OpenCode configuration; do not edit generated files under
`~/.config/opencode/` directly.

Worktrunk setup creates and indexes Serena for the current worktree before
readiness is published. OpenCode still starts Serena with
`--project-from-cwd` and owns one stdio process per client session. Worktrunk's
blocking `pre-remove` hook cleans disposable Serena runtime state before
removal and preserves a tracked `.serena/project.yml`.

### Normal operator flow

For Orca environment recipes, `gorgias-chat/orca.yaml` invokes the installed
`wt-orca start` and `wt-orca stop` commands. `start` provisions the checkout
through Worktrunk, waits for readiness, attaches Orca, and returns the one
`provisioned-root` result Orca consumes:

```zsh
wt-orca start --branch feature/example --name feature-example --base main
wt-orca stop --name feature-example       # refuses dirty worktrees by default
wt-orca stop --name feature-example --force  # explicit destructive override
```

The `--force` stop option must be supplied explicitly by the destroy hook or
operator; it is never inferred from an uncommitted worktree.

`wt-orca stop` does not invoke Serena cleanup directly. Worktrunk's blocking
`pre-remove` hook runs Serena cleanup once during the delegated `wt remove`
operation while the worktree path still exists.

For manual operation outside an Orca recipe:

Run the following from the primary repository. The Worktrunk post-start hooks
publish `pending` while setup runs and then publish `ready` (or an explicit
`degraded` state):

```zsh
wt switch --create feature/example
wt-orca attach
wt-orca status
wt-orca detach
wt remove --force   # explicit Worktrunk-owned removal
```

`wt-orca start` uses Worktrunk's `switch --create --no-cd --format json`
contract and captures its absolute path without changing the caller's shell.
It waits for setup readiness, registers the primary repository
with Orca if necessary, and attaches to the existing path with a
`path:<absolute-worktree-path>` selector. `status` reports readiness and the
Orca terminal; `detach` closes only that terminal. `wt-orca stop` detaches the
owned terminal and delegates removal to Worktrunk; it does not invoke Serena
cleanup directly. Worktrunk's blocking `pre-remove` hook runs once during that
delegated removal. Neither adapter operation creates or removes a Git worktree
directly; generated local artifacts can make a non-forced Worktrunk removal
refuse to proceed.

### Recovery and cleanup

- **`ready`** — attach normally. A successful attach reports the Orca terminal
  handle and keeps the Worktrunk checkout in place.
- **`failed`** — do not attach. Fix the reported setup error, then rerun the
  Worktrunk setup hook/script for the same workspace and root. Both
  `$WORKSPACE_PATH` and `$ROOT_PATH` come from Worktrunk/setup output; the
  complete manual retry uses the failed workspace as the explicit status and
  attachment target:

  ```zsh
  WORKSPACE_PATH="/absolute/path/to/worktree"
  ROOT_PATH="/absolute/path/to/primary-repository"
  wt-orca status "$WORKSPACE_PATH"
  ~/developer/dotfiles/worktree-setup.sh \
    --workspace-path "$WORKSPACE_PATH" \
    --root-path "$ROOT_PATH"
  wt-orca attach \
    --workspace-path "$WORKSPACE_PATH" \
    --root-path "$ROOT_PATH" \
    --timeout 120
  ```

  Replace both paths with the canonical workspace/root pair from the
  Worktrunk/setup output. Setup is idempotent and republishes readiness after
  a successful retry.

- **`degraded`** — the setup completed with an explicitly non-blocking
  fallback. The adapter refuses this state by default; use
  `wt-orca attach --allow-degraded` only when that fallback is acceptable, or
  retry setup to reach `ready`.
- **timeout** — attachment stops with a timeout and OpenCode is not launched.
  Check `wt-orca status "$WORKSPACE_PATH"`, allow setup more time, or retry the
  setup before attaching again. A timeout does not remove the worktree.
- **pre-remove cleanup failure** — Worktrunk aborts removal while the worktree
  still exists. Fix the reported Serena path, Git metadata, or permission
  problem, then rerun the same `wt remove` operation. Serena cleanup does not
  use a retry queue and never invokes Git worktree removal itself.

Orca repository registration is intentionally retained after `wt-orca detach`
and after the Worktrunk path is removed. The observed Orca CLI exposes
`repo list` and `repo add`, but no `repo remove` command. This retained
registration is expected runtime metadata, not a second worktree.

### Credentials and runtime ownership

Before deploying Context7 configuration, complete this secret-free checklist:

1. Revoke the historical Context7 credential.
2. Provision or update the `CONTEXT7_API_TOKEN` environment secret.
3. Run `python3 scripts/validate-ai-rules.py`. Deployment itself performs the
   staged validation and secret scan before replacement.
4. Perform an authorized Context7 MCP request using the provisioned environment
   token; the request must return successfully.
5. Consider deployment unblocked only after all four prerequisites—revocation,
   environment provisioning, validation, and a successful auth probe—are
   complete.

The tracked MCP configuration uses `{env:CONTEXT7_API_TOKEN}` and must never
contain the credential itself.

The validated OMO-inside-Orca probe observed `OpenCode` exit `0`, the
sanitized identifier `OMO_HANDSHAKE=observed:oh-my-opencode-identifier`, and no
conventional nested `tmux`, `screen`, or `zellij` session (`TMUX`, `STY`, and
`ZELLIJ` were empty; `NEW_CONVENTIONAL_MUX=none`). `TERM_PROGRAM=Orca` and
Orca's terminal/session topology remain the outer runtime boundary; OMO does
not own that outer terminal.

## Configuration Layers

| Layer               | File                                                       | What it controls                                                           |
| ------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------------- |
| Provider + MCPs     | `~/.config/opencode/opencode.json`                         | Bifrost models (`bf`, `bf-a`, `bf-o`), MCP server endpoints                |
| OMO Slim plugin     | `~/.config/opencode/opencode.json`                         | Plugin registration, LSP, disabled default agents                          |
| Agent models + MCPs | `~/.config/opencode/oh-my-opencode-slim.json`              | Preset `bifrost`, per-agent model/variant/skills/MCPs, custom agents, tmux |
| Prompt overrides    | `~/.config/opencode/oh-my-opencode-slim/{agent}_append.md` | Per-agent appended instructions from rules/                                |
| Global instructions | `~/.config/opencode/AGENTS.md`                             | OMO Slim managed                                                           |
| Project config      | `<repo>/opencode.json`                                     | Project-level MCPs, model overrides                                        |

## How to Update

### Change an agent's model

Edit `oh-my-opencode-slim.json` → update the `model` field under the `bifrost` preset.

### Add a rule

1. Create `.rulesync/rules/<name>.md` for global behavior.
2. Add content to `{agent}_append.md` only when it is genuinely agent-specific;
   do not copy global routing or tool-selection rules into agent appends.
3. Update `opencode.json` if needed.

### Change a custom agent's prompt

Edit the corresponding `.rulesync/subagents/<name>.md` file, then regenerate the deployed prompt assets with `./deploy.sh`.

## MCP & Browser CLI Inventory

Repository MCP definitions live in `.rulesync/mcp.jsonc`; agent assignments live in `oh-my-opencode-slim.json`. Navigator's browser CLI comes from the `agent-browser` skill and runs via Bash. `./deploy.sh` generates the corresponding global configuration:

| MCP                 | Enabled     | Assigned to                                            |
| ------------------- | ----------- | ------------------------------------------------------ |
| context7            | ✓           | Librarian                                              |
| github              | ✓           | Orchestrator                                           |
| sentry              | ❌ disabled | —                                                      |
| notion              | ❌ disabled | —                                                      |
| linear              | ✓           | Librarian                                              |
| gcp-logging         | ❌ disabled | Detective uses `gcloud` CLI via Bash instead           |
| cortex              | ✓           | Sage, Librarian (Internal docs/Notion via Cortex MCP)  |
| rootly              | ❌ disabled | —                                                      |
| agent-browser CLI   | ✓           | Navigator via Bash and the `agent-browser` skill       |
| gorgias-mcp         | disabled    | —                                                      |
| figma-mcp           | ✓           | Designer                                                |

**Datadog & GCP Logs:** via `pup` and `gcloud` CLIs (Bash), not MCP. Always call `pup` with `--agent --read-only` flags.

## Provider: Bifrost

Models routed through `https://bifrost.ops.gorgias.io` with 3 provider types:

- `bf` — OpenAI-compatible (DeepSeek V4 via Fireworks/Novita, Gemini, GLM)
- `bf-a` — Anthropic (Claude Haiku 4.5, Sonnet 4.6/5, Opus 4.8)
- `bf-o` — OpenAI (GPT-4o, GPT-5.x Terra/Luna/Sol)

Auth via `{file:/Users/guilhermebomfim/.config/gorgias-ai/bifrost-virtual-key}`.
