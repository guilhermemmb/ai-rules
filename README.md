# ai-rules — OpenCode Agent Configuration

Source of truth for OpenCode agent rules, custom agents, skills, and commands. Used by [Oh My OpenCode Slim](https://ohmyopencodeslim.com/) with [Bifrost](https://bifrost.ops.gorgias.io) model routing. Supports multiple model profiles (default vs cost-efficient).

## Documentation atlas

Concise navigation into the `ai-rules` system documentation:

| Area | Document | Description |
| :--- | :--- | :--- |
| **Architecture** | [`docs/architecture.md`](docs/architecture.md) | Source/generated/installed layers, authority boundaries, and agent categories |
| **Workflows** | [`docs/workflows.md`](docs/workflows.md) | Task sizing, SDD flow, discovery, fixer/reviewer pipelines, and deployment lifecycle |
| **Reference** | [`docs/reference.md`](docs/reference.md) | Compact registries of rules, skills, subagents, scripts, profiles, and MCPs |
| **Review & proposals** | [`docs/review-and-improvements.md`](docs/review-and-improvements.md) | Independently reviewed improvement proposals, severities, and roadmap |
| **Mermaid graphs** | [`architecture`](docs/graphs/architecture.mmd) · [`dispatch-and-review`](docs/graphs/dispatch-and-review.mmd) · [`workspace-lifecycle`](docs/graphs/workspace-lifecycle.mmd) | Flow and layer diagrams (`.mmd` source) |
| **Interactive agents** | [`agents-overview/README.md`](agents-overview/README.md) | Interactive agent visualization (data + HTML) |

## Quick Start

```bash
# Deploy configuration; deploy.sh refreshes the repository-recorded OMO package when needed
./deploy.sh

# Reinstall the pinned OMO package and deploy, overriding ownership-manifest hash
# drift in only opencode.json / opencode.jsonc. Deploy-only, no snapshot/rollback
# backup — a later failure may require manual recovery (other safety checks stay strict)
./deploy.sh --force

# Deploy cost-efficient profile (DeepSeek V4 + Gemini Flash)
./deploy.sh --model-profile=cost-efficient

# Inside OpenCode
ping all agents
```

### Reviewer concurrency

Reviewer runs applicable concern lanes in independent background batches.
When selected/applicable—when the normalized diff contains a non-empty
executable/source/config diff and the aspect filter permits it—the
reviewer-simplifier runs exactly once after Phase A with the Phase A findings.
Set `REVIEWER_MAX_PARALLEL` in the runtime environment to control the batch size:
values from `1` to `3` are accepted; unset, empty, non-integer, zero, and
negative values fall back to `3`, and values above `3` are clamped to `3`.
Failed, timed-out, unavailable, malformed, or incomplete lane results populate
`errors` and make Review Health Degraded/inconclusive. This is a runtime setting
documented in the reviewer prompt/skill, not an OpenCode top-level configuration
key.
For OpenCode, review commands and review requests run the preloaded `reviewer`
workflow through the orchestrator, which is the sole coordinator of the
applicable reviewer-lane lifecycle. OpenCode never dynamically calls
`functions.skill`, dispatches a nested `@reviewer`, or silently falls back to a
partial direct-lane review. Specialist lanes are read-only leaves: they do not
load the reviewer skill or dispatch additional tasks.

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
concurrency remains a separate reviewer-workflow setting.

### OpenCode deployment ownership

`deploy.sh` writes `~/.config/opencode/.ai-rules.manifest.json` with the
deployment owner, manifest version, timestamp, exact managed files/directories,
and SHA-256 values for managed files. The manifest is installed atomically with
the generated OpenCode configuration and is included in transaction snapshots
and rollback.

On a first deployment without a manifest, only existing files whose paths and
contents exactly match the staged Rulesync payload are adopted. Unknown agents,
skills, commands, directories, and other OpenCode configuration are preserved.
Later deployments remove only paths recorded in the previous manifest; managed
directories are removed only when empty, then the current payload and manifest
are installed. Malformed manifests, path traversal, absolute paths, symlinks,
missing managed paths, and changed managed files fail safely before replacement.

`./deploy.sh --check` validates ownership without changing live configuration.
It also reports a differing higher-priority reviewer shadow skill at
`~/.agents/skills/reviewer/SKILL.md` (or an equivalent reviewer entry). Shadow
entries are never deleted automatically; reconcile or remove them manually.
Rulesync sources in this repository remain the source of truth.

`./deploy.sh --force` re-installs the pinned OMO package and additionally
overrides an ownership-manifest hash mismatch in **only** the two mutable
usage/config artifacts `opencode.json` and `opencode.jsonc`. Every other check
— malformed or missing manifests, unsafe/absolute/escaping paths, symlinks,
missing or non-regular managed files, changed non-exempt managed files, a staged
payload whose managed files/directories do not match the prior manifest, unknown
-file collisions, pending/ambiguous transactions, reviewer shadows, and payload
validation — remains strict and fail-closed.

Force is a deploy-only operation: it is rejected when combined with `--check`
or `--compatibility-check`. The narrow override is validated after the staged
payload is built and the prior manifest is captured, and before any live
mutation. Force mode intentionally creates **no** snapshot or rollback backup
state: it does not run `snapshot_live_configuration`, write a transaction
marker, or create a rollback directory, and it replaces the live configuration
atomically without retaining a backup. If a later operation fails, force mode
reports that automatic rollback is unavailable and that manual recovery may be
required. Normal `./deploy.sh` retains its full snapshot/rollback behavior.

### OpenCode compatibility and runtime evidence

The deployment preflight reads and prints the installed `opencode --version`,
the repository-recorded OMO package reference, and the installed OMO,
`@opencode-ai/plugin`, and `@opencode-ai/sdk` package metadata. This is
read-only diagnostics: deployment does not infer or assert a compatible host /
plugin pair from version numbers, and this task does not install, downgrade, or
upgrade packages. The OMO package's SDK dependency is reported as a range when
it is not itself pinned.

An optional, operator-supplied compatibility evidence file can be selected with
`OPENCODE_COMPATIBILITY_EVIDENCE`. It must be a regular JSON file containing
`opencode_version`, `omo_version`, `plugin_version`, and `sdk_version`. A
mismatch is reported as version skew; missing evidence remains unverified.
Neither static validation nor a version match is a runtime Healthy claim.
The opt-in compatibility check runs `./deploy.sh --compatibility-check` before
starting OpenCode and blocks when this status is unknown or skewed, so no
runtime report can claim Healthy from an unverified package pair.

After deployment, start a fresh OpenCode process before relying on generated
configuration. The repository's remaining validation mechanisms provide static,
configuration, compatibility, and deployment-precondition evidence; they do not
prove background-task parentage, reconciliation, effective permissions, or the
absence of forbidden reviewer tool execution. Those runtime conclusions remain
unverified without independent runtime evidence.

## Model Profiles

Model routing is **balanced across speed, quality, and cost** — neither profile
makes a performance-first or percentage-savings claim. Each profile assigns a
per-agent model and an optional `variant`; the same two profiles are applied to
the OMO config (`oh-my-opencode-slim.json`) and to the versioned YAML files
below.

| Profile            | Strategy                      | Key models                                                                  | Location                             |
| :----------------- | :---------------------------- | :-------------------------------------------------------------------------- | :----------------------------------- |
| **default**        | Balanced (speed/quality/cost) | GPT-5.6 Luna/Terra, Novita DeepSeek V4 Pro, DeepSeek V4 Flash, Gemini 3 Flash, GLM 5.2 | `profiles/models/default.yml`        |
| **cost-efficient** | Cost-efficient (balanced)     | Novita DeepSeek V4 Pro, DeepSeek V4 Flash/Pro, Gemini 3 Flash, GPT-5.6 Terra, GLM 5.2 | `profiles/models/cost-efficient.yml` |

**Profile schema:** version 1 — each agent entry carries a required `model` and
an optional `variant`. A profile entry that omits `variant` leaves that agent's
existing variant unchanged during application; variants are drawn from the OMO
agent configuration, never invented here. Both profiles route Fixer to the
Novita DeepSeek V4 Pro thinking model (`high`), preserved unchanged.

**Neutral tiers.** Routing places each agent on one of three tiers — a `high`
reasoning tier (Luna/Terra), a balanced `medium` tier (Luna/Terra/GLM 5.2/
DeepSeek Pro), and a fast `low`/flash tier (DeepSeek V4 Flash/Gemini 3 Flash).
These tiers trade speed, quality, and cost without claiming a measurable speedup
or cost reduction; no unmeasured performance or savings percentage is reported
anywhere in this configuration.

## Agent Pantheon

### Built-in (7 — OMO Slim)

| Agent            | Model (Default profile)   | Model (Cost-efficient profile) | Role                            |
| :--------------- | :---------------- | :--------------------- | :------------------------------ |
| **Orchestrator** | GPT-5.6 Luna      | Gemini 3 Flash         | Master delegator & coordinator  |
| **Oracle**       | GPT-5.6 Terra     | GPT-5.6 Terra          | Strategic advisor, architecture |
| **Explorer**     | DeepSeek V4 Flash | DeepSeek V4 Flash      | Codebase reconnaissance         |
| **Librarian**    | GPT-5.6 Luna      | DeepSeek V4 Flash      | Knowledge retrieval             |
| **Designer**     | GLM 5.2           | GLM 5.2                | UI/UX excellence                |
| **Fixer**        | DeepSeek V4 Pro via Novita (high) | DeepSeek V4 Pro via Novita (high) | Implementation specialist |
| **Observer**     | Gemini 3 Flash    | Gemini 3 Flash         | Visual analysis                 |

### Custom (13 + 1 compatibility alias)

| Agent                       | Model (Default profile)   | Model (Cost-efficient profile) | Dispatch when                                              |
| :-------------------------- | :---------------- | :--------------------- | :--------------------------------------------------------- |
| **Navigator**               | Gemini 3 Flash    | Gemini 3 Flash         | agent-browser CLI, snapshots/refs, screenshots, extraction |
| **Detective**               | GPT-5.6 Luna      | DeepSeek V4 Flash      | Production errors, logs, metrics                           |
| **Sage**                    | GPT-5.6 Terra     | GPT-5.6 Terra          | Gorgias metrics, schemas, rules                            |
| **Reviewer lanes (10)**     | Mixed: Luna, Terra, DeepSeek V4 Flash, Gemini 3 Flash | Mixed: DeepSeek V4 Flash, DeepSeek V4 Pro, GPT-5.6 Terra | OpenCode orchestrator review workflow |
| **reviewer-code**           | GPT-5.6 Luna (medium) | DeepSeek V4 Pro        | CLAUDE.md compliance, bugs                                 |
| **reviewer-test**           | GPT-5.6 Luna (medium) | DeepSeek V4 Pro        | Behavioral test coverage                                   |
| **reviewer-errors**         | GPT-5.6 Luna (medium) | DeepSeek V4 Pro        | Silent failures, error handling                            |
| **reviewer-types**          | GPT-5.6 Luna (medium) | DeepSeek V4 Pro        | Type encapsulation, invariants                             |
| **reviewer-security**       | GPT-5.6 Terra (medium) | GPT-5.6 Terra          | Security boundaries, secrets, input safety                 |
| **reviewer-performance**    | GPT-5.6 Luna (medium) | DeepSeek V4 Pro        | Algorithms, I/O, queries, hot paths                        |
| **reviewer-data-integrity** | GPT-5.6 Terra (medium) | GPT-5.6 Terra          | Persistence, transactions, state integrity                 |
| **reviewer-accessibility**  | Gemini 3 Flash    | DeepSeek V4 Flash      | WCAG and UI accessibility                                  |
| **reviewer-comments**       | DeepSeek V4 Flash | DeepSeek V4 Flash      | Comment and documentation accuracy                         |
| **reviewer-simplifier**     | DeepSeek V4 Flash | DeepSeek V4 Flash      | Post-Phase-A clarity and maintainability pass              |

**Council** disabled. Observer auto-routes images from Orchestrator. The
`reviewer` agent is a retained compatibility-coordinator alias (excluded from
the 13 custom agents above); OpenCode review ownership runs through the
orchestrator's preloaded reviewer workflow.

**Model Profiles Rationale:** routing is **neutral across speed, quality, and
cost**. Both profiles use Novita DeepSeek V4 Pro for the Fixer with the preserved
`high` variant and route reasoning through `reasoning_content`; sampling
overrides (`temperature`, `top_p`, and `top_k`) are not configured because this
thinking model does not support them. Both profiles route Oracle and Sage to
GPT-5.6 Terra and Designer to GLM 5.2. The **default profile** routes Librarian
and Detective to GPT-5.6 Luna and uses a balanced mix for the reviewer lanes.
The `cost-efficient` profile routes the orchestrator to Gemini 3 Flash and uses
a lower-cost Flash/Pro mix for the subagents and reviewer lanes. No unmeasured
performance or percentage-savings claim is made for either profile.

### Novita Fixer compatibility

The source configuration uses the exact model ID
`bf/huggingface/novita/deepseek-ai/DeepSeek-V4-Pro` in both profiles and the
OMO `bifrost.fixer` assignment. The matching Bifrost provider entry enables
`interleaved.field = reasoning_content` and preserves its existing fallback
chain and credential reference. The provider catalog confirms the model entry;
the Bifrost grant, `high` variant acceptance, and multi-turn reasoning/tool-use
round trip remain runtime compatibility checks rather than static guarantees.
The source profiles and provider configuration record this assignment, while
runtime compatibility remains an operational concern rather than a static
guarantee.

After deployment, restart OpenCode in a fresh process before relying on the
configuration. Treat a missing grant, unsupported variant/parameters,
reasoning-content round-trip error, or `finish_reason: length` observed during
independent runtime verification as a compatibility failure—not a successful
fallback.

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
│   │   └── code-exploration.md     # RTK/native and GitNexus routing
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
review gate through the OpenCode orchestrator's preloaded reviewer workflow;
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
| 3. Execute                           | S/M combined-plan; `executing-plans` for L/XL | @fixer (code), @designer (UI/UX), OpenCode orchestrator (S/M post-implementation or L/XL per-task), @oracle (escalation) |
| 4. Review (optional; user-confirmed) | `reviewing-plans` | OpenCode orchestrator (final gate — up to 10 applicable reviewer-* specialists, only after opt-in) |

See `docs/sdd-workflow.md` for the full flowchart and agent usage matrix.

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

For **code discovery**, use explicit RTK subcommands: `rtk grep`, `rtk read`, `rtk find`. See the `code-exploration` rule for the full routing protocol between RTK/native tools and GitNexus.

```bash
# Check for missing RTK/plugin or deployment drift without installing or mutating
./deploy.sh --check

# Manual prerequisite when RTK is absent (deploy.sh uses this automatically)
brew install rtk-ai/tap/rtk
```

Homebrew is required only when RTK is absent. Test with `git status` — RTK rewrites it transparently.

## Code intelligence and MCP lifecycle

The system has two explicit discovery tiers:

1. **RTK/native OpenCode tools** are authoritative for exact text and file
   discovery, shell commands, tests, Git, configuration, documentation, and
   edits.
2. **GitNexus** is an indexed macro graph for Orchestrator, Oracle, Explorer,
   and Detective. Confirm context and freshness, then use the documented
   `context/freshness -> query/context -> affected process resources -> impact ->
   detect_changes` sequence. Inspect the schema before using Cypher; do not
   invent query syntax. GitNexus 1.6.5 exposes server-side rename, but OpenCode
   denies the normalized `gitnexus_rename` tool in this managed configuration.
   This is an OpenCode-side control, not a universal process-level boundary;
   direct GitNexus processes are outside that control. The canonical operation
   table is in
   [`docs/workflows.md`](docs/workflows.md#gitnexus-sequence-and-tool-selection).

   Only Orchestrator, Oracle, Explorer, and Detective have GitNexus access.
   Designer, Fixer, `reviewer-code`, and `reviewer-types` have no
   code-intelligence MCP; they use native OpenCode tools for exact definitions,
   references, diagnostics, files, shell, tests, and edits.

### MCP access matrix

| Agent | GitNexus | Other assigned access |
| :--- | :--- | :--- |
| Orchestrator | ✓ | `github` |
| Oracle | ✓ | — |
| Explorer | ✓ | — |
| Detective | ✓ | `pup`/`gcloud` via Bash |
| Designer | — | `figma-mcp`; no code-intelligence MCP |
| Fixer | — | no code-intelligence MCP |
| `reviewer-code` | — | no code-intelligence MCP |
| `reviewer-types` | — | no code-intelligence MCP |
| Librarian | — | `context7`, `websearch`, `gh_grep`, `linear`, `cortex` |
| Sage | — | `cortex` |
| Navigator, Observer, `reviewer`, and remaining reviewer lanes | — | None |

GitNexus `1.6.5` is persistently installed by `deploy.sh`. Its source MCP
command retains `GITNEXUS_MCP_READ_ONLY=1` for forward compatibility, but this
environment does not treat that variable as a universal process-level boundary.
OpenCode denies the normalized `gitnexus_rename` tool; direct GitNexus processes
are outside that managed OpenCode control. Worktrunk lifecycle setup uses
GitNexus only:

```bash
gitnexus analyze --index-only "$WORKSPACE_PATH"
```

GitNexus setup is path-scoped and does not inject `AGENTS.md`, `CLAUDE.md`, or
skills. A failed GitNexus command publishes `failed` rather than silently
publishing `ready`.

Cleanup runs `gitnexus remove --force "$WORKSPACE_PATH"`, accepts an absent
index as idempotent, and targets only GitNexus state. Cleanup failures use the
durable retry queue; cleanup never runs `gitnexus clean --all`, `wt remove`, or
`git worktree remove`.

### Serena removal and deferred/manual uninstall runbook — legacy Codebase Memory state

Serena's active MCP/agent policy removal is complete. Deploy-time installation
and runtime removal are later verified lifecycle steps; this task does not
claim that the launcher, global state, or repository state has already been
deleted. The required sequence is:

1. Remove source/configuration grants and deploy the GitNexus-only configuration.
2. Verify the live output and the four-agent matrix.
3. Uninstall `serena-agent` with `uv tool uninstall serena-agent`.
4. Remove only the verified Serena launcher, global state, and repository state.
5. Avoid broad uv-cache deletion.

The legacy `codebase-memory-mcp` binary, caches, registrations, repository
state, and sibling-worktree state remain deferred until sibling Worktrunk setup,
index, and cleanup scripts no longer depend on them (Task 4). Removal is
deferred until an operator has verified every affected path:

1. Stop OpenCode and other clients that may hold the old process or state.
2. Deploy the migrated configuration and verify the GitNexus-only matrix.
3. Migrate sibling worktree setup, index, and cleanup scripts away from the old
   integration; do not assume this repository owns those files.
4. Review old registrations and state locations, preserving anything still
   needed by an active workspace.
5. Remove the old binary, cache, and state only by verified paths, then confirm
   no client or cleanup hook still references them.

No automatic deployment or validation step performs these destructive actions.

### GitNexus skill ownership

Rulesync owns the GitNexus skill source at `.rulesync/skills/gitnexus-*/`.
Deployment projects those skills to `~/.config/opencode/skills/gitnexus-*/`.
Copies under `~/.agents/skills/` and `~/.claude/skills/` are removed only after
Rulesync generation and global output content have been verified. Unmanaged,
unrelated vendor skills are preserved.

## Worktrunk → Orca → OpenCode workflow

Worktrunk is the only Git worktree lifecycle owner. It creates and removes
worktrees; Orca attaches to an existing Worktrunk path and must not create a
second checkout. OpenCode and oh-my-opencode-slim (OMO) run inside the
Orca-owned terminal. `ai-rules/deploy.sh` is the source of truth for generated
OpenCode configuration; do not edit generated files under
`~/.config/opencode/` directly.

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

`wt-orca stop` does not invoke cleanup directly. Worktrunk's `pre-remove` hook
remains the cleanup and retry-queue owner, so cleanup runs once during the
delegated `wt remove` operation.

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
owned terminal and delegates removal to Worktrunk; it does not invoke cleanup
directly. Worktrunk's `pre-remove` hook owns the cleanup and retry queue and
runs once during that delegated removal. Neither adapter operation creates or
removes a Git worktree directly; generated local artifacts can make a
non-forced Worktrunk removal refuse to proceed.

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
- **pending cleanup** — a failed pre-remove cleanup writes a durable queue
  record keyed by the canonical root/workspace pair. Retry it without needing
  the removed directory:

  ```zsh
  ~/developer/dotfiles/worktree-cleanup.sh --retry-pending --limit 100
  ```

  Failed retries remain queued and observable; repeat the retry after fixing
  the external failure. `--state-key <64-hex-key>` scopes a retry, and
  `--prune-state` removes only ordinary state for gone workspaces—it preserves
  pending cleanup records. Cleanup never invokes `wt remove` or Git worktree
  removal.

Orca repository registration is intentionally retained after `wt-orca detach`
and after the Worktrunk path is removed. The observed Orca CLI exposes
`repo list` and `repo add`, but no `repo remove` command. This retained
registration is expected runtime metadata, not a second worktree.

### Credentials and runtime ownership

Before deploying Context7 configuration, complete this secret-free checklist:

1. Revoke the historical Context7 credential.
2. Provision or update the `CONTEXT7_API_TOKEN` environment secret.
3. Run `python3 scripts/validate-ai-rules.py` and `./deploy.sh --check`. The
   latter is a dry-run and does not perform authentication.
4. Perform an authorized Context7 MCP request using the provisioned environment
   token; the request must return successfully.
5. Consider deployment unblocked only after all four prerequisites—revocation,
   environment provisioning, validation/dry-run, and a successful auth probe—are
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
| gitnexus            | ✓           | Orchestrator, Oracle, Explorer, Detective               |
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
