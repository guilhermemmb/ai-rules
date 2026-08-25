# ai-rules — OpenCode Agent Configuration

Source of truth for OpenCode agent rules, custom agents, skills, and commands. Used by [Oh My OpenCode Slim](https://ohmyopencodeslim.com/) with [Bifrost](https://bifrost.ops.gorgias.io) model routing. Supports multiple model profiles (default vs cost-efficient).

## Quick Start

```bash
# Deploy configuration; deploy.sh installs or refreshes oh-my-opencode-slim@latest when needed
./deploy.sh

# Force-install or refresh oh-my-opencode-slim@latest and deploy (not all dependencies)
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
values from `1` to `10` are accepted; unset, empty, non-integer, zero, and
negative values fall back to `10`, and values above `10` are clamped to `10`.
Failed, timed-out, unavailable, malformed, or incomplete lane results populate
`errors` and make Review Health Degraded/inconclusive. This is a runtime setting
documented in the reviewer prompt/skill, not an OpenCode top-level configuration
key.

## Model Profiles

| Profile            | Strategy                     | Key Models                                                     | Location                             |
| :----------------- | :--------------------------- | :------------------------------------------------------------- | :----------------------------------- |
| **default**        | Performance-first            | GPT-5.6 Luna, Claude Sonnet 5, DeepSeek V4 Pro, Gemini 3 Flash | `profiles/models/default.yml`        |
| **cost-efficient** | Cost-optimized (90% savings) | Gemini 3 Flash, DeepSeek V4 Flash/Pro                          | `profiles/models/cost-efficient.yml` |

## Agent Pantheon

### Built-in (7 — OMO Slim)

| Agent            | Model (Default)   | Model (Cost-Efficient) | Role                            |
| :--------------- | :---------------- | :--------------------- | :------------------------------ |
| **Orchestrator** | GPT-5.6 Luna      | Gemini 3 Flash         | Master delegator & coordinator  |
| **Oracle**       | Claude Sonnet 5   | DeepSeek V4 Pro        | Strategic advisor, architecture |
| **Explorer**     | DeepSeek V4 Flash | DeepSeek V4 Flash      | Codebase reconnaissance         |
| **Librarian**    | DeepSeek V4 Flash | DeepSeek V4 Flash      | Knowledge retrieval             |
| **Designer**     | Claude Sonnet 5   | Gemini 3 Flash         | UI/UX excellence                |
| **Fixer**        | Claude Sonnet 5   | DeepSeek V4 Flash      | Implementation specialist       |
| **Observer**     | Gemini 3 Flash    | Gemini 3 Flash         | Visual analysis                 |

### Custom (14)

| Agent                       | Model (Default)   | Model (Cost-Efficient) | Dispatch when                                              |
| :-------------------------- | :---------------- | :--------------------- | :--------------------------------------------------------- |
| **Navigator**               | Gemini 3 Flash    | Gemini 3 Flash         | agent-browser CLI, snapshots/refs, screenshots, extraction |
| **Detective**               | DeepSeek V4 Flash | DeepSeek V4 Flash      | Production errors, logs, metrics                           |
| **Sage**                    | DeepSeek V4 Flash | DeepSeek V4 Flash      | Gorgias metrics, schemas, rules                            |
| **Reviewer**                | GPT-5.6 Luna      | DeepSeek V4 Flash      | PR/branch/diff review coordinator                          |
| **reviewer-code**           | GPT-5.6 Luna      | DeepSeek V4 Pro        | CLAUDE.md compliance, bugs                                 |
| **reviewer-test**           | GPT-5.6 Luna      | DeepSeek V4 Flash      | Behavioral test coverage                                   |
| **reviewer-errors**         | GPT-5.6 Luna      | DeepSeek V4 Pro        | Silent failures, error handling                            |
| **reviewer-types**          | GPT-5.6 Luna      | DeepSeek V4 Pro        | Type encapsulation, invariants                             |
| **reviewer-security**       | GPT-5.6 Luna      | DeepSeek V4 Pro        | Security boundaries, secrets, input safety                 |
| **reviewer-performance**    | GPT-5.6 Luna      | DeepSeek V4 Pro        | Algorithms, I/O, queries, hot paths                        |
| **reviewer-data-integrity** | GPT-5.6 Luna      | DeepSeek V4 Pro        | Persistence, transactions, state integrity                 |
| **reviewer-accessibility**  | GPT-5.6 Luna      | DeepSeek V4 Flash      | WCAG and UI accessibility                                  |
| **reviewer-comments**       | DeepSeek V4 Flash | DeepSeek V4 Flash      | Comment and documentation accuracy                         |
| **reviewer-simplifier**     | GPT-5.6 Luna      | DeepSeek V4 Flash      | Post-Phase-A clarity and maintainability pass              |

**Council** disabled. Observer auto-routes images from Orchestrator.

**Model Profiles Rationale:** The system defaults to a specialized mix of DeepSeek V4 Pro, Claude Sonnet 5, GPT-5.6 Luna, and Gemini 3 Flash for complex reasoning. The `cost-efficient` profile swaps these for DeepSeek V4 (Flash/Pro) and Gemini 3 Flash, providing ~90-95% cost reduction with competitive performance for most routine development tasks.

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
│   │   └── code-exploration.md     # Centralized RTK/Graph MCP discovery routing
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

### SDD Workflow (4-step)

| Phase                                | Skill             | Key agents                                                                              |
| ------------------------------------ | ----------------- | --------------------------------------------------------------------------------------- |
| 1. Brainstorm                        | `brainstorming`   | @explorer, @librarian, @oracle, @designer                                               |
| 2. Plan                              | `writing-plans`   | — (orchestrator writes plan directly)                                                   |
| 3. Execute                           | `executing-plans` | @fixer (code), @designer (UI), @reviewer (per-task gate), @oracle (escalation)          |
| 4. Review (optional; user-confirmed) | `reviewing-plans` | @reviewer (final gate — up to 10 applicable reviewer-\* specialists, only after opt-in) |

See `docs/sdd-workflow.md` for the full flowchart and agent usage matrix.

## Agent tmp paths

| Agent     | Output path       |
| --------- | ----------------- |
| Navigator | `/tmp/navigator/` |
| Sage      | `/tmp/sage/`      |

> PR description files use `/tmp/pr-<branch>.md` (ephemeral, not grouped here).

## RTK — Token Optimization Plugin

RTK is installed as an OpenCode plugin that transparently rewrites ordinary development commands before execution — `git status` automatically becomes `rtk git status` with no manual prefixing.

For **code discovery**, use explicit RTK subcommands: `rtk grep`, `rtk read`, `rtk find`. See the `code-exploration` rule for the full routing protocol between RTK CLI and Graph MCP.

```bash
# Install (already done — plugin at ~/.config/opencode/plugins/rtk.ts)
rtk init -g --opencode

# Verify
rtk --version
```

> **Note:** After installing the plugin, restart OpenCode. Test with `git status` — RTK rewrites it transparently.

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
owned terminal, runs cleanup, and delegates removal to Worktrunk. Neither
adapter operation creates or removes a Git worktree directly. Worktrunk's
pre-remove cleanup handles the
codebase-memory project, local `.codebase-memory/`, and context-mode indexes;
the generated local graph can make a non-forced removal refuse to proceed.

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

Context7 credentials are injected at runtime through the approved
`CONTEXT7_API_KEY` environment variable; the tracked MCP configuration uses
`{env:CONTEXT7_API_KEY}` and must not contain the credential itself. A
historical Context7 credential previously exposed during configuration work
still requires external revocation/rotation. Until that action is complete,
real deployment is blocked; the credential value is deliberately not printed
or stored here.

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
| codebase-memory-mcp | ✓           | Orchestrator, Oracle, Explorer, Fixer, Detective, Sage |
| context7            | ✓           | Librarian                                              |
| github              | ✓           | Orchestrator                                           |
| sentry              | ✓           | Detective                                              |
| linear              | ✓           | Librarian                                              |
| gcp-logging         | ❌ disabled | Detective uses `gcloud` CLI via Bash instead           |
| cortex              | ✓           | Sage, Librarian (Internal docs/Notion via Cortex MCP)  |
| rootly              | ✓           | Detective                                              |
| agent-browser CLI   | ✓           | Navigator via Bash and the `agent-browser` skill       |
| gorgias-mcp         | disabled    | —                                                      |
| figma               | ✓           | —                                                      |

**Datadog & GCP Logs:** via `pup` and `gcloud` CLIs (Bash), not MCP. Always call `pup` with `--agent --read-only` flags.

## Provider: Bifrost

Models routed through `https://bifrost.ops.gorgias.io` with 3 provider types:

- `bf` — OpenAI-compatible (DeepSeek V4, Gemini, GLM)
- `bf-a` — Anthropic (Claude Haiku 4.5, Sonnet 4.6/5, Opus 4.8)
- `bf-o` — OpenAI (GPT-4o, GPT-5.x Terra/Luna/Sol)

Auth via `{file:/Users/guilhermebomfim/.config/gorgias-ai/bifrost-virtual-key}`.
