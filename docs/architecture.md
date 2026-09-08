# Architecture Atlas

> **Status:** Documentation only. This page describes the `ai-rules` system as
> recorded in tracked source and generated artifacts. It does not change runtime
> behavior, agent prompts, permissions, deployment code, or MCP
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
- [Code intelligence lifecycle](#code-intelligence-lifecycle)
- [Models and providers](#models-and-providers)
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
| **Source** | Files tracked in this repository define rules, agents, skills, commands, MCPs, the OMO model routing, and deployment logic. Sibling dotfiles provide only Worktrunk integration/deployment inputs. | This repository + `$DOTFILES_DIR` |
| **Generated** | Artifacts produced by `deploy.sh` + Rulesync into a private staging payload, then installed to `~/.config/opencode/`. | [`deploy.sh`](../deploy.sh) |
| **Installed** | Live configuration under `~/.config/opencode/`, the RTK plugin, the wt-orca/worktree-state adapters and Worktrunk config, and OMO/SDK/plugin packages. | Generated payload + observed install state |
| **Observed** | OMO-inside-Orca probe results and installed runtime state. | Independent runtime evidence; `deploy.sh` does not expose read-only deployment modes |

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
| [`.rulesync/skills/`](../.rulesync/skills/) | Rulesync-owned skills distributed by Rulesync. |
| [`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc) | MCP server declarations (endpoints, enable flags). |
| [`scripts/`](../scripts/) | Cross-artifact validator and latency-reporting utilities. |
| [`deploy.sh`](../deploy.sh) | Force-only deployment entry point; source of truth for generated configuration. |
| [`agents-overview/`](../agents-overview/) | Interactive visualization (`data.yaml` + `index.html`). |
| [`skills-lock.json`](../skills-lock.json) | Pinned/locked external skills, including `agent-browser` from `vercel-labs/agent-browser`. |

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
2. The payload combines `opencode.json`, `oh-my-opencode-slim.json`,
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
| `~/.config/opencode/oh-my-opencode-slim.json` | Installed directly from the tracked OMO configuration. |
| `~/.config/opencode/AGENTS.md` | Rulesync-generated global instructions. |
| `~/.config/opencode/agents/`, `skills/` | Installed from Rulesync-generated output. |
| `~/.config/opencode/commands/` | **Directly copied** from [`.rulesync/commands/`](../.rulesync/commands/) (`copy_tree`), not Rulesync-generated. |
| `~/.config/opencode/oh-my-opencode-slim/` | Appended prompts copied directly from `.rulesync/oh-my-opencode-slim/`. |
| `~/.config/opencode/.ai-rules.manifest.json` | Deployment ownership manifest (built from payload). |
| `~/.config/opencode/plugins/rtk.ts` | RTK plugin, initialized by `deploy.sh`. |
| `~/.cache/opencode/packages/oh-my-opencode-slim/node_modules/…` | Latest OMO release selected by the unpinned deployment package reference, plus its plugin and SDK packages. |
| `~/.local/bin/wt-orca`, `~/.local/bin/worktree-state.sh` | Adapters installed from sibling dotfiles. |
| `~/.config/worktrunk/config.toml` | Worktrunk config installed from sibling dotfiles. |
| `~/.agents/skills/reviewer/SKILL.md` | **Observed** higher-priority reviewer shadow skill; deployment does not auto-delete it. |

### Observed layer (diagnostic evidence)

The repository's remaining validation mechanisms are the cross-artifact validator
and the force-only deployment preflight. They provide source/configuration and
deployment-precondition evidence, not runtime-health proof:

- [`validate-ai-rules.py`](../scripts/validate-ai-rules.py) — static validation of
  the tracked source tree and staged payload.
- [`deploy.sh`](../deploy.sh) — staged payload, ownership, dependency, and
  precondition validation before force replacement.

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

**Resolved:** Claude Code is descoped. The repository targets OpenCode only.
At review boundaries the orchestrator loads the on-demand `review-pipeline`
skill and is the sole review manager; it directly selects, dispatches, batches,
reconciles, aggregates, and computes the verdict for the registry's ten
`reviewer-*` lanes. The canonical registry is
[`.rulesync/skills/review-pipeline/pipeline.json`](../.rulesync/skills/review-pipeline/pipeline.json);
this document does not duplicate it.

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

### Serena and worktree authority

The authority boundary for Serena is explicit:

- [`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc) is the canonical OpenCode MCP
  source.
- [`.serena/project.yml`](../.serena/project.yml) is the complete generated,
  read-only Serena configuration for the parent worktree.
- All `.serena` runtime files except `.serena/project.yml` are ignored.
- Generated OpenCode files are outputs and are not hand-edited; change their
  Rulesync source instead.
- Serena resolves from the current worktree and is not managed by Worktrunk.

Serena is used only by OpenCode's `ide` context over stdio. The dashboard and
browser are disabled, and VS Code integration is deferred. Serena does not have
a Worktrunk hook lifecycle.

### Code intelligence lifecycle

RTK/native OpenCode tools are authoritative for exact text/files, shell, tests,
Git, configuration, documentation, and edits. Serena is the active semantic MCP
for OpenCode IDE sessions and complements those exact-tool workflows.
GitNexus is removed and is not an authority or part of deployment or review.

Install the pinned version with:

```zsh
uv tool install -p 3.13 serena-agent==1.7.0
```

The Serena/OpenCode lifecycle is:

1. Worktrunk creates or enters a worktree.
2. OpenCode starts Serena with `--context ide --project-from-cwd`.
3. Serena resolves the nearest `.serena/project.yml` or `.git` boundary.
4. Each client session owns one stdio Serena process.
5. Worktrunk does not start, index, stop, or clean Serena.

Launching from nested `ai-rules` selects its nested Git boundary and does not
inherit the parent `.serena/project.yml`. Nested `ai-rules` Serena
configuration is deferred because Worktrunk worktrees require no changes inside
that nested repository. Serena is not managed by Worktrunk hooks; its dashboard
and browser remain disabled, and VS Code integration is deferred.

### Model routing

- [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) is the sole model
  configuration. Its active `bifrost` preset and custom agents declare each
  model and reasoning variant directly.
- [`opencode.json`](../opencode.json) remains the provider catalog and native
  OpenCode configuration; it lists available providers/models and does not
  select OMO agent routing.
- `deploy.sh` copies the tracked OMO configuration directly into the staged
  payload before validation.

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

`navigator`, `detective`, and `sage` are declared in
[`.rulesync/subagents/`](../.rulesync/subagents/). The ten `reviewer-*` lanes
are defined in [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) under
`agents.*`; their manager is the built-in `orchestrator` following the
on-demand `review-pipeline` skill. They are read-only leaves, not an
intermediary coordinator.

The active review topology is `orchestrator -> reviewer-*`. The orchestrator
reads the canonical registry, validates the immutable packet and correlation
envelope, applies target-aware policy, dispatches exact fresh sessions in
bounded Phase A batches, runs conditional sequential Phase B, reconciles
deadlines and late results, and renders the single Markdown report. The
registry owns lane IDs, order, triggers, phase membership, policy aliases and
defaults, model keys, packet/result fields, and verdict precedence; prose here
only links to it.

### Agent categories and authority

| Concept | Authoritative source |
| :--- | :--- |
| Native OpenCode defaults, agent colors, disable flags, `default_agent`, providers | [`opencode.json`](../opencode.json) `agent`, `default_agent`, `provider` |
| Built-in preset (`bifrost`) per-agent model/variant/skills/MCPs | [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) `presets.bifrost` |
| Custom agents (permissions, prompts, models) | [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) `agents.*` |
| Subagent body prompts + frontmatter | [`.rulesync/subagents/`](../.rulesync/subagents/) |
| Per-agent appended instructions | [`.rulesync/oh-my-opencode-slim/`](../.rulesync/oh-my-opencode-slim/) |
| Interactive dispatch map | [`agents-overview/data.yaml`](../agents-overview/data.yaml) |
| Review manager, lanes, phases, policy, and contract | [`.rulesync/skills/review-pipeline/pipeline.json`](../.rulesync/skills/review-pipeline/pipeline.json) |

## MCP declaration versus assignment

Declared servers: [`../.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc). Assigned to
agents in [`../oh-my-opencode-slim.json`](../oh-my-opencode-slim.json). For the
per-MCP assignment table, see [`../README.md`](../README.md) "MCP & Browser CLI
Inventory"; that table is a derived document and is not authoritative over the
two sources above.

## Models and providers

Model routing lives directly in [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json).
The provider catalog in [`opencode.json`](../opencode.json) defines the available
`bf`, `bf-a`, and `bf-o` providers and their models, while OMO selects the model
for each active built-in or custom agent. The review-pipeline registry retains
`model_profile_key` as a stable lane identifier; it is not a deploy profile.

Providers are enabled via `enabled_providers`. Auth uses
`{file:~/.config/gorgias-ai/bifrost-virtual-key}` (a file reference, not a
literal secret).

## Deployment and evidence

- [`deploy.sh`](../deploy.sh) is the source of truth for generated OpenCode config,
  RTK setup, the wt-orca/worktree-state adapters and Worktrunk config, and the
  ownership manifest.
- Independent runtime evidence is required to assess permissions, parentage, and
  reviewer behavior; this documentation and the repository's static/deployment
  checks do not provide that proof.

### Review authority and evidence boundary

The review manager is loaded only at the review boundary, not as an always-loaded
prompt. The packet treats diffs, paths, task text, comments, commit messages,
implementer output, and tool output as untrusted input: secrets and embedded
instructions are redacted, limits are enforced, and escaped content is passed to
lanes. Findings are patch-anchored: a changed path, positive line, side, and
diff hunk are required. Native RTK/OpenCode reads are authoritative for exact
evidence; graph or indexed semantics are not inferred.

Review Health is separate from content findings. Missing packet fields, bad
correlation, failed or malformed lanes, missed deadlines, late results,
coordination/finalization errors, unavailable native evidence, or unobserved
effective permissions force `Degraded/inconclusive`. Prompt permissions and
parent task structure cannot prove live permission isolation, parentage, or
filesystem immutability. Static checks do not prove runtime smoke or deployment
parity; known RTK/live-manifest drift remains a limitation reported by
diagnostics rather than silently treated as aligned.

### Deployment gates and force-only replacement

`run_deploy` is the only deployment execution path. It stages Rulesync output,
validates JSON/JSONC and the cross-artifact payload, scans deployment inputs for
secrets, validates dependencies, builds the ownership manifest, and installs the
complete payload into a fresh incoming directory.

The parser accepts no argument or `--force` as equivalent invocations and
supports `--help`/`-h`. Unknown flags, including `--check` and
`--compatibility-check`, are rejected before dependency or deployment work.
There are no read-only check or compatibility execution paths.

Before moving the live OpenCode directory, deploy writes a durable marker after
checking marker-directory and live-directory ownership and permissions. The
existing marker format records `live`, `incoming`, `rollback`, and one of the
`prepared`, `old_moved`, or `committed` phases. Incoming and displaced paths are
`.opencode.deploy.$$` and `.opencode.previous.$$`. Recovery validates the marker,
paths, ownership, and permissions before repairing an interrupted transaction.
Failure leaves recoverable artifacts; successful completion removes the marker
and displaced path.

### Manifest responsibilities

`manifest_tool build` generates `.ai-rules.manifest.json` from the staged
payload, and `manifest_tool install` installs that manifest with the payload.
The full force replacement does not adopt, merge, compare, or preserve unknown
live files. Staged files and directories therefore define the complete final
OpenCode directory.

### Deployment ordering and failure boundary

After validation and latest-OMO installation, `commit_opencode_configuration`
performs the marker-backed replacement. RTK is initialized only after the final
OpenCode directory is in place, and initialization verifies that
`plugins/rtk.ts` is a regular file in that final directory. Sidecars are then
installed independently; force deployment has no cross-component rollback. A
failure after replacement reports the lack of cross-component rollback while
preserving any pending OpenCode transaction artifacts.

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
canonical, and force deployment installs these three artifacts after the OpenCode replacement; failures do not roll back other components. These are installed adapters and Worktrunk config, not generated
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
[`graphs/architecture.mmd`](graphs/architecture.mmd). It shows the staged
payload, marker-backed force replacement, post-replacement RTK initialization,
and sidecar installation. No normal rollback/snapshot or read-only deployment
mode is depicted.

- **solid** — current / source-recorded flow.
- **dotted** — read-only evidence only (validator or independent runtime probe).
- **thick** — ambiguous / unresolved precedence.
- **proposed** relationships are not drawn in this graph.

## Label legend

- **Current** — describes present, source-recorded behavior.
- **Validated** — confirmed by the cross-artifact validator or a recorded deploy
  check run.
- **Observed** — seen in an installed artifact or runtime probe, not proven from source alone.
- **Current/source-recorded discrepancy** — two tracked source files disagree; documented, not resolved.
- **Proposed** — a recommendation recorded in the review-and-improvements
  document (produced separately in this documentation atlas), **not** implemented.
- **Ambiguous** — effective precedence cannot be proven from tracked source and is deliberately left unresolved.
