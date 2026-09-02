# Architecture Atlas

> **Status:** Documentation only. This page describes the `ai-rules` system as
> recorded in tracked source and generated artifacts. It does not change runtime
> behavior, agent prompts, permissions, model profiles, deployment code, or MCP
> configuration. Source rules and configuration remain authoritative; this page
> links to them instead of reproducing long policy text.

This atlas explains the complete `ai-rules` system: its source layers, how
Rulesync and `deploy.sh` produce the live OpenCode/OMO configuration, the agents
and MCPs it configures, and — explicitly — the places where the effective
authority between competing configuration sources cannot be proven from tracked
source.

- [Layer model](#layer-model)
- [Authority model and unresolved precedence](#authority-model-and-unresolved-precedence)
- [Agents](#agents)
- [MCP declaration versus assignment](#mcp-declaration-versus-assignment)
- [Model profiles and providers](#model-profiles-and-providers)
- [Deployment and evidence](#deployment-and-evidence)
- [Interactive visualization](#interactive-visualization)
- [Graph](#graph)
- [Label legend](#label-legend)

## Layer model

The system is best understood as four layers. The first three are reproducible
from tracked source (plus sibling-dotfiles inputs that `deploy.sh` copies); the
fourth is observed at runtime and cannot be proven from source alone.

| Layer | What it is | Authoritative source |
| :--- | :--- | :--- |
| **Source** | Files tracked in this repository define rules, agents, skills, commands, MCPs, model profiles, and deployment logic. Sibling dotfiles provide only Worktrunk integration/deployment inputs. | This repository + `$DOTFILES_DIR` |
| **Generated** | Artifacts produced by `deploy.sh` + Rulesync + `apply-model-profile.py` into a private staging payload, then installed to `~/.config/opencode/`. | [`deploy.sh`](../deploy.sh) |
| **Installed** | Live configuration under `~/.config/opencode/`, the RTK plugin, the wt-orca/worktree-state adapters and Worktrunk config, and OMO/SDK/plugin packages. | Generated payload + observed install state |
| **Observed** | `--check`/`--compatibility-check` output and OMO-inside-Orca probe results. | [`deploy.sh`](../deploy.sh) for `--check`/`--compatibility-check`; installed runtime state for OMO-inside-Orca probes |

### Source layer (tracked in-repo)

| Path | Role |
| :--- | :--- |
| [`opencode.json`](../opencode.json) | Native OpenCode config: shell, default agent, LSP, plugin registration, agent colors, disable flags, top-level model/`small_model`, and the `bf`/`bf-a`/`bf-o` provider catalog. |
| [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) | OMO plugin config: the built-in `bifrost` preset (per-agent model/variant/skills/MCPs) and custom agents under `agents.*` (permissions + prompts), plus `disabled_agents`. |
| [`rulesync.jsonc`](../rulesync.jsonc) | Rulesync config: declares `targets` (`opencode`), `features` (`rules`, `subagents`, `skills`, `mcp`), `inputRoot`, and home-dir `outputRoots`. |
| [`.rulesync/rules/`](../.rulesync/rules/) | Rule files distributed as prompt overrides (`overview`, `custom-rules`, `code-exploration`, `context7`, `git-safety`, `pr-workflow`, `security-scan`, `figma-*`). |
| [`.rulesync/subagents/`](../.rulesync/subagents/) | Custom subagent definitions (`detective`, `navigator`, `sage`) with YAML frontmatter declaring model/tools/mcps/skills. |
| [`.rulesync/commands/`](../.rulesync/commands/) | Command definitions (`review-pr.md`). |
| [`.rulesync/oh-my-opencode-slim/`](../.rulesync/oh-my-opencode-slim/) | Per-agent appended prompts (`{agent}_append.md`). |
| [`.rulesync/skills/`](../.rulesync/skills/) | Vendored skills distributed by Rulesync. |
| [`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc) | MCP server declarations (endpoints, enable flags). |
| [`profiles/models/`](../profiles/models/) | Model profiles (`default.yml`, `cost-efficient.yml`) — schema version 1 with a required per-agent `model` and an optional `variant`. |
| [`scripts/`](../scripts/) | Cross-artifact validator, profile applier, and latency-reporting utilities. |
| [`deploy.sh`](../deploy.sh) | Deployment/check/rollback entry point; source of truth for generated configuration. |
| [`agents-overview/`](../agents-overview/) | Interactive visualization (`data.yaml` + `index.html`). |
| [`skills-lock.json`](../skills-lock.json) | Pinned/locked external skills (`agent-browser` from `vercel-labs/agent-browser`). |

### Sibling-dotfiles inputs (outside this repo)

`deploy.sh` resolves several inputs from `$DOTFILES_DIR` (the parent of this
repository) rather than from this repo. They are validated before install but
their authoritative source lives elsewhere. These are the **Worktrunk
integration artifacts** — two executable adapters, the Worktrunk config, and the
installer that owns the config:

| Input | Role | Deployed to |
| :--- | :--- | :--- |
| `$DOTFILES_DIR/wt-orca.sh` | Executable adapter (Orca attach/detach for Worktrunk worktrees) | `~/.local/bin/wt-orca` |
| `$DOTFILES_DIR/worktree-state.sh` | Executable worktree-state helper | `~/.local/bin/worktree-state.sh` |
| `$DOTFILES_DIR/worktrunk/config.toml` | Worktrunk config (canonical config, installed via the installer) | `~/.config/worktrunk/config.toml` |
| `$DOTFILES_DIR/worktrunk-install.sh` | Worktrunk **installer** — invoked by `install_worktrunk_config` as `worktrunk-install.sh --config-path … --force` to install the canonical config | (runs, not copied) |
| `$DOTFILES_DIR/deployment-lock.sh` | Shared deployment-lock helper | sourced, not copied |

### Generated layer

`deploy.sh` builds a staged payload before touching live config. From
[`deploy.sh`](../deploy.sh) `build_staged_payload`:

1. `rulesync generate --targets opencode` produces `AGENTS.md`,
   `opencode.jsonc`, `.opencode/agents/*`, and `.opencode/skills/*` into a
   private staging directory. (Rulesync does **not** generate commands.)
2. [`apply-model-profile.py`](../scripts/apply-model-profile.py) patches
   `oh-my-opencode-slim.json` with the selected profile's model IDs.
3. The payload combines `opencode.json`, `oh-my-opencode-slim.json`,
   `rulesync.jsonc`, the Rulesync-generated `AGENTS.md`/`opencode.jsonc`/agents/
   skills, the `{agent}_append.md` files, and commands. The
   `{agent}_append.md` files and commands are **copied directly** into the
   payload (see [`deploy.sh`](../deploy.sh) `copy_tree`), not Rulesync-generated.

`manifest_tool build` then generates `.ai-rules.manifest.json` **from the staged
payload** (owner, version, timestamp, managed files/directories, and SHA-256
hashes). The payload is also validated by
[`validate-ai-rules.py`](../scripts/validate-ai-rules.py) before any live mutation
(see [Deployment gates and compatibility diagnostics](#deployment-gates-and-compatibility-diagnostics)).

### Installed layer (observed, not source-reproducible)

| Path | Notes |
| :--- | :--- |
| `~/.config/opencode/opencode.json` | Installed from payload. |
| `~/.config/opencode/oh-my-opencode-slim.json` | Installed after profile patch. |
| `~/.config/opencode/AGENTS.md` | Rulesync-generated global instructions. |
| `~/.config/opencode/agents/`, `skills/` | Installed from Rulesync-generated output. |
| `~/.config/opencode/commands/` | **Directly copied** from [`.rulesync/commands/`](../.rulesync/commands/) (`copy_tree`), not Rulesync-generated. |
| `~/.config/opencode/oh-my-opencode-slim/` | Appended prompts copied directly from `.rulesync/oh-my-opencode-slim/`. |
| `~/.config/opencode/.ai-rules.manifest.json` | Deployment ownership manifest (built from payload). |
| `~/.config/opencode/plugins/rtk.ts` | RTK plugin, initialized by `deploy.sh`. |
| `~/.cache/opencode/packages/oh-my-opencode-slim@latest/node_modules/…` | OMO, `@opencode-ai/plugin`, `@opencode-ai/sdk` packages. |
| `~/.local/bin/wt-orca`, `~/.local/bin/worktree-state.sh` | Adapters installed from sibling dotfiles. |
| `~/.config/worktrunk/config.toml` | Worktrunk config installed from sibling dotfiles. |
| `~/.agents/skills/reviewer/SKILL.md` | **Observed** higher-priority reviewer shadow skill detected by `--check`; never auto-deleted. |

### Observed layer (diagnostic evidence)

The repository's remaining validation mechanisms are the cross-artifact validator
and the read-only deploy diagnostics. They provide source/configuration,
compatibility, and deployment-precondition evidence, not runtime-health proof:

- [`validate-ai-rules.py`](../scripts/validate-ai-rules.py) — static validation of
  the tracked source tree and staged payload.
- [`deploy.sh --check`](../deploy.sh) and
  [`deploy.sh --compatibility-check`](../deploy.sh) — read-only ownership,
  compatibility, and precondition diagnostics.

A static validation pass or version match is **not** a runtime "Healthy" claim.
Runtime conclusions must remain unverified without independent runtime evidence.

## Authority model and unresolved precedence

Multiple sources can configure the same concept. Where the effective precedence
cannot be proven from tracked source, it is recorded as **Ambiguous** below — it
is not inferred.

### Competing agent prompt/config sources

The same agent is described in at least three places, and these overlap without a
recorded precedence rule:

1. [`.rulesync/subagents/*.md`](../.rulesync/subagents/) frontmatter — `model`,
   `tools`, `mcps`, `skills`, and a body prompt.
2. [`.rulesync/oh-my-opencode-slim/*_append.md`](../.rulesync/oh-my-opencode-slim/) — per-agent appended instructions.
3. [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) `agents.*` — `model`,
   `variant`, `mcps`, `skills`, `permission`, `prompt`, `orchestratorPrompt`.
4. [`opencode.json`](../opencode.json) `agent.*` — colors and `default_agent`.

**Current/source-recorded state:** the subagent prompt bodies and the OMO
`agents.*.prompt` now agree on output paths; both sources use
`~/.cache/opencode/agent-output/<agent>/`:

- Navigator: both [`.rulesync/subagents/navigator.md`](../.rulesync/subagents/navigator.md)
  and `oh-my-opencode-slim.json` write to `~/.cache/opencode/agent-output/navigator/`.
- Sage: both [`.rulesync/subagents/sage.md`](../.rulesync/subagents/sage.md) and
  `oh-my-opencode-slim.json` write to `~/.cache/opencode/agent-output/sage/`.

The earlier `/tmp/` discrepancy is resolved.

### Two (plus one) OpenCode config files

- [`opencode.json`](../opencode.json) — native OpenCode config (source of truth for providers, default agent, agent colors, plugin registration).
- `opencode.jsonc` — **generated** by Rulesync (declared rules/agents/skills); staged alongside `opencode.json`. Commands are copied directly, not part of the Rulesync-generated `opencode.jsonc` content.
- [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) — OMO plugin config.

**Ambiguous** how OpenCode resolves `opencode.json` versus the Rulesync-generated
`opencode.jsonc`; both are installed. The manifest tracks both.

### Rulesync vs OMO vs native OpenCode

- [`rulesync.jsonc`](../rulesync.jsonc) declares `targets: ["opencode"]` with its
  output root at the home directory.
- [`deploy.sh`](../deploy.sh) stages `rulesync generate --targets opencode`
  (`build_staged_payload`).

**Resolved:** Claude Code is descoped. The repository targets OpenCode only; the
`reviewer` agent remains a compatibility-coordinator alias (retained, not a
deployment target), and OpenCode review ownership runs through the orchestrator's
preloaded reviewer workflow.

### MCP declaration versus assignment

- [`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc) **declares** MCP servers.
- [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) **assigns** MCPs to agents
  (`presets.bifrost.*.mcps` and `agents.*.mcps`).
- [`.rulesync/subagents/*.md`](../.rulesync/subagents/) frontmatter also declares `mcps`.

These are three independent statements of MCP relationship. `websearch` and
`gh_grep` are assigned to the Librarian but are **built into the OMO runtime** and
are **not** declared in `mcp.jsonc` (see `BUILTIN_MCP_REFERENCES` in
[`validate-ai-rules.py`](../scripts/validate-ai-rules.py)).

**Current/source-recorded naming:** the declared server is
`figma-mcp` ([`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc)), and documentation
now refers to `figma-mcp` consistently.

### Model profile application

- [`opencode.json`](../opencode.json) sets a top-level `model` and `small_model`.
- [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) sets per-agent models.
- [`profiles/models/*.yml`](../profiles/models/) uses schema version 1: each agent
  entry carries a required `model` and an optional `variant`. A profile entry that
  omits `variant` leaves that agent's existing variant unchanged during
  application.
- [`apply-model-profile.py`](../scripts/apply-model-profile.py) merges a profile into
  `oh-my-opencode-slim.json` at deploy time.

**Ambiguous** the precedence between the top-level `opencode.json` model and the
per-agent OMO model when a profile is applied. Source records both but no single
rule orders them.

## Agents

Agents fall into three groups. [`opencode.json`](../opencode.json) supplies native
OpenCode metadata — agent colors, disable flags, and `default_agent` — while the
OMO and Rulesync sources define and configure the agents themselves
([`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) for built-in/custom
definitions, [`.rulesync/subagents/`](../.rulesync/subagents/) for subagent body
prompts).

### Built-in (OMO `bifrost` preset)

`orchestrator`, `oracle`, `explorer`, `librarian`, `designer`, `fixer`,
`observer`. `council` is disabled (`disabled_agents`). The `explore` and
`general` agents are disabled in [`opencode.json`](../opencode.json).

### Custom agents

`navigator`, `detective`, `sage` (declared in
[`.rulesync/subagents/`](../.rulesync/subagents/)) and the `reviewer` compatibility
coordinator plus ten `reviewer-*` lanes (defined in
[`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) under `agents.*`).

The `reviewer` agent is a retained **compatibility-coordinator alias** (not an
OpenCode coordinator). In OpenCode, the orchestrator preloads the `reviewer`
skill and is the sole coordinator, dispatching the applicable `reviewer-*` lanes
directly (with `reviewer-simplifier` conditional on Phase B); the lanes are
read-only leaves. See [`README.md`](../README.md) "Reviewer concurrency" and the
[`reviewer` rule](../.rulesync/skills/reviewer/SKILL.md).

### Agent categories and authority

| Concept | Authoritative source |
| :--- | :--- |
| Native OpenCode defaults, agent colors, disable flags, `default_agent`, providers | [`opencode.json`](../opencode.json) `agent`, `default_agent`, `provider` |
| Built-in preset (`bifrost`) per-agent model/variant/skills/MCPs | [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) `presets.bifrost` |
| Custom agents (permissions, prompts, models) | [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) `agents.*` |
| Subagent body prompts + frontmatter | [`.rulesync/subagents/`](../.rulesync/subagents/) |
| Per-agent appended instructions | [`.rulesync/oh-my-opencode-slim/`](../.rulesync/oh-my-opencode-slim/) |
| Interactive dispatch map | [`agents-overview/data.yaml`](../agents-overview/data.yaml) |

## MCP declaration versus assignment

Declared servers: [`../.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc). Assigned to
agents in [`../oh-my-opencode-slim.json`](../oh-my-opencode-slim.json). For the
per-MCP assignment table, see [`../README.md`](../README.md) "MCP & Browser CLI
Inventory"; that table is a derived document and is not authoritative over the
two sources above.

## Model profiles and providers

Both profiles use schema version 1: each agent entry carries a required `model`
and an optional `variant`; a profile entry that omits `variant` leaves that
agent's existing variant unchanged. Profiles are optional: deployment installs
and applies the selected profile, not both (see `deploy.sh --model-profile=<name>`).
Profile application is performed by `scripts/apply-model-profile.py`.

| Profile | Source |
| :--- | :--- |
| `default` | [`../profiles/models/default.yml`](../profiles/models/default.yml) |
| `cost-efficient` | [`../profiles/models/cost-efficient.yml`](../profiles/models/cost-efficient.yml) |

Providers `bf` (OpenAI-compatible), `bf-a` (Anthropic), and `bf-o` (OpenAI) are
defined in [`opencode.json`](../opencode.json) under `provider` and enabled via
`enabled_providers`. Auth uses
`{file:~/.config/gorgias-ai/bifrost-virtual-key}` (a file reference, not a
literal secret).

## Deployment and evidence

- [`deploy.sh`](../deploy.sh) is the source of truth for generated OpenCode config,
  RTK setup, the wt-orca/worktree-state adapters and Worktrunk config, and the
  ownership manifest.
- Independent runtime evidence is required to assess permissions, parentage, and
  reviewer behavior; this documentation and the repository's static/deployment
  checks do not provide that proof.

### Deployment gates and compatibility diagnostics

`run_deploy` has **blocking deployment checks** and **separate compatibility
diagnostics**:

**Blocking deployment checks** (a failure aborts deployment before snapshot-covered
convergence):

1. **Payload gate** — [`validate-ai-rules.py`](../scripts/validate-ai-rules.py),
   invoked inside `build_staged_payload` as
   `validate-ai-rules.py --root <source> --payload <payload> --profile <name>`.
   Its scope is the **tracked source tree and the staged payload** — it does
   **not** validate the live installed directory.
2. **Deployment-input preflight** — `scan_deployment_inputs` (secret-like
   credential scan over the payload and deployment inputs),
   `validate_tracked_worktrunk_config` (canonical Worktrunk config), the
   dependency/RTK preflight, and the executable checks for the wt-orca /
   worktree-state / Worktrunk-installer sources.
3. **Existing manifest validation** — when `~/.config/opencode/.ai-rules.manifest.json`
   already exists, `manifest_tool validate` checks its ownership and consistency
   before deployment; an invalid manifest refuses deployment.
4. **Reviewer-shadow detection** — `detect_reviewer_shadow` verifies the canonical
   OpenCode reviewer skill against `~/.agents/skills/reviewer/` and refuses
   deployment on a differing shadow entry (which is never auto-deleted).

**Compatibility diagnostics (read-only, non-blocking in normal deployment):**
`preflight_compatibility` reads and prints the installed `opencode --version`, the
repository-recorded OMO reference, and the installed
OMO/`@opencode-ai/plugin`/`@opencode-ai/sdk` metadata, then reports
`COMPATIBILITY_STATUS` (`unverified`, `skew`, or `matched`). During `run_deploy`
it is read-only and does **not** block. Its status is enforced only by
`deploy.sh --compatibility-check` (`run_compatibility_check`), which blocks
the compatibility-check flow when `COMPATIBILITY_STATUS` is not `matched`.

These blocking checks and compatibility diagnostics are distinct from the
**read-only `--check` live comparison** (`run_check`), which uses
`manifest_tool compare` (staged payload vs live directory), `compare_path`
(Worktrunk integration artifacts), `omo_installed`, and the RTK plugin check to
report drift without mutating anything.

### Pre-snapshot is not mutation-free

The blocking checks and compatibility diagnostics precede
`snapshot_live_configuration`, but deployment is **not** mutation-free before the
snapshot. Before snapshotting, `run_deploy` may:

- recover a pending OpenCode transaction (`recover_pending_opencode_transaction`),
- install a missing `codebase-memory-mcp` (`preflight_dependencies` →
  `install_codebase_memory_mcp`), and
- install RTK/Homebrew if the RTK binary is absent (`preflight_rtk` →
  `resolve_rtk_binary`).

These pre-snapshot actions are **outside the current deployment's private
snapshot rollback boundary**. Rollback coverage begins only after the snapshot
completes and does not undo the pre-snapshot actions above.

### Manifest responsibilities

- **Build** — `manifest_tool build` generates `.ai-rules.manifest.json` from the
  staged payload (owner, version, timestamp, managed files/directories, hashes).
- **Adopt** — on a first deployment without a manifest, `manifest_tool adopt`
  adopts only existing live files whose paths and contents exactly match the
  staged payload.
- **Validate / compare** — `manifest_tool validate` checks the live manifest's
  ownership and consistency before deployment; `manifest_tool compare` compares
  the staged payload against the live directory for drift.
- **Remove** — `manifest_tool remove` removes only paths recorded in the previous
  manifest; managed directories are removed only when empty.
- **Force** — `manifest_tool force` validates the narrow force override before
  any mutation: only `opencode.json` / `opencode.jsonc` hash drift may differ;
  the staged payload's managed files/directories must match the prior manifest,
  and any exempt file present in the prior manifest must also be present in the
  staged payload (so an override never emits an empty staged hash).

Rollback is **not** a manifest responsibility. See
[Deployment phases and failure boundary](#deployment-phases-and-failure-boundary).

### Deployment phases and failure boundary

After the blocking checks pass, `run_deploy` proceeds through ordered phases:

1. **Snapshot** — `snapshot_live_configuration` captures the `~/.config/opencode/`
   directory (including the RTK plugin at `plugins/rtk.ts`) and the Worktrunk
   integration artifacts into a private live snapshot. This is the point at which
   rollback coverage begins.
2. **Prepare** — `initialize_rtk_plugin` (RTK plugin) and `install_omo` (pinned
   OMO package).
3. **Transactional commit** — `commit_opencode_configuration` installs the staged
   payload into `~/.config/opencode/` atomically, using a transaction marker and
   a rollback path.
4. **Integration artifact install** — `install_wt_orca` (`~/.local/bin/wt-orca` +
   `worktree-state.sh`) installs the executable adapters, and
   `install_worktrunk_config` (`~/.config/worktrunk/config.toml` via the Worktrunk
   installer) installs the Worktrunk config.

A **blocking-check failure aborts deployment without snapshot-covered
convergence** — no snapshot rollback is performed because none of the
snapshot-covered outputs have been mutated yet (see
[Pre-snapshot is not mutation-free](#pre-snapshot-is-not-mutation-free)). Rollback
applies only after the snapshot completes (from phase 2 onward): `cleanup_stage`
restores the private live snapshot via `restore_live_configuration` (the OpenCode
directory, including the RTK plugin at `plugins/rtk.ts`) and
`restore_managed_file` (the wt-orca, worktree-state, and Worktrunk config files). A transaction marker supports recovery of an interrupted
deployment. Rollback restores the previous live configuration; it does not derive
from or rewrite the ownership manifest, and it does not undo pre-snapshot actions
such as a recovered pending transaction or a newly installed codebase-memory-mcp
or RTK/Homebrew.

### Force mode: no snapshot or rollback backup

`deploy.sh --force` is a deploy-only override for the two mutable config files.
After the staged payload is built and the prior manifest is captured, the force
override is validated before `initialize_rtk_plugin`, `install_omo`, snapshot
creation, or any live mutation; the commit path then consumes that validated
plan and never re-validates after mutation. Force mode intentionally skips
`snapshot_live_configuration` and creates no transaction marker or rollback
directory: it replaces the live configuration atomically without retaining a
backup. On a post-validation failure there is no automatic rollback, and the
failure is reported with an explicit manual-recovery requirement. Normal
deployment retains the snapshot/rollback contract described above.

### Worktrunk integration artifacts boundary

`deploy.sh` installs and validates the **Worktrunk integration artifacts**
after `commit_opencode_configuration`. These are two distinct kinds of thing,
both originating in the sibling dotfiles (see
[Sibling-dotfiles inputs](#sibling-dotfiles-inputs-outside-this-repo)):

- **Executable adapters** — `install_wt_orca` installs `~/.local/bin/wt-orca`
  (from `wt-orca.sh`) and `~/.local/bin/worktree-state.sh` (from
  `worktree-state.sh`).
- **Worktrunk config** — `install_worktrunk_config` invokes the
  `worktrunk-install.sh` installer to install `~/.config/worktrunk/config.toml`
  (from `worktrunk/config.toml`).

`validate_tracked_worktrunk_config` enforces that the tracked Worktrunk config is
canonical, and `deploy.sh --check` uses `compare_path` to detect drift in these
three artifacts. These are installed adapters and Worktrunk config, not generated
OpenCode configuration; the generated OpenCode config is governed by the
ownership manifest described above.

## Interactive visualization

The [`agents-overview/`](../agents-overview/) directory provides a browser-based,
interactive graph (`index.html` + `data.yaml`) with a static dispatch map in
[`agents-overview/README.md`](../agents-overview/README.md). It is a maintained
visualization, not an authoritative configuration source — edit `data.yaml` to
reflect changes, but treat it as derived from the sources above.

## Graph

The Mermaid source for the layer/authority/deployment graph is at
[`graphs/architecture.mmd`](graphs/architecture.mmd). Edge styles are defined by
the in-graph legend:

- **solid** — current / source-recorded flow.
- **dotted** — read-only evidence only (validator, `--check`, and
  `--compatibility-check`).
- **circle** — rollback / restore (private live snapshot → snapshotted outputs).
- **thick** — ambiguous / unresolved precedence where the effective precedence
  cannot be proven from tracked source.
- **proposed** relationships are not drawn in this graph; they belong to the
  review-and-improvements document produced separately in this atlas.

## Label legend

- **Current** — describes present, source-recorded behavior.
- **Validated** — confirmed by the cross-artifact validator or a recorded deploy
  check run.
- **Observed** — seen in an installed artifact or runtime probe, not proven from source alone.
- **Current/source-recorded discrepancy** — two tracked source files disagree; documented, not resolved.
- **Proposed** — a recommendation recorded in the review-and-improvements
  document (produced separately in this documentation atlas), **not** implemented.
- **Ambiguous** — effective precedence cannot be proven from tracked source and is deliberately left unresolved.
