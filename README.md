# ai-rules — OpenCode Agent Configuration

Source of truth for OpenCode agent rules, custom agents, skills, and commands. Used by [Oh My OpenCode Slim](https://ohmyopencodeslim.com/) with [Bifrost](https://bifrost.ops.gorgias.io) model routing. Supports multiple model profiles (default vs cost-efficient).

## Quick Start

```bash
# Install OMO Slim with tmux
bunx oh-my-opencode-slim@latest install --tmux=yes

# Deploy configuration (default profile)
./deploy.sh

# Deploy cost-efficient profile (DeepSeek V4 + Gemini Flash)
./deploy.sh --model-profile=cost-efficient

# Inside OpenCode
ping all agents
```

## Model Profiles

| Profile | Strategy | Key Models | Location |
| :--- | :--- | :--- | :--- |
| **default** | Performance-first | Gemini 3 Flash, GPT-5.6 Terra/Luna, Gemini 3 Pro | `profiles/models/default.yml` |
| **cost-efficient** | Cost-optimized (90% savings) | DeepSeek V4 Flash/Pro, Gemini 3 Flash | `profiles/models/cost-efficient.yml` |

## Agent Pantheon

### Built-in (7 — OMO Slim)

| Agent | Model (Default) | Model (Cost-Efficient) | Role |
| :--- | :--- | :--- | :--- |
| **Orchestrator** | Gemini 3 Flash | Gemini 3 Flash | Master delegator & coordinator |
| **Oracle** | GPT-5.6 Terra | DeepSeek V4 Pro | Strategic advisor, architecture |
| **Explorer** | DeepSeek V4 Flash | DeepSeek V4 Flash | Codebase reconnaissance |
| **Librarian** | DeepSeek V4 Flash | DeepSeek V4 Flash | Knowledge retrieval |
| **Designer** | Gemini 3 Pro | Gemini 3 Flash | UI/UX excellence |
| **Fixer** | GPT-5.6 Luna | DeepSeek V4 Flash | Implementation specialist |
| **Observer** | Gemini 3 Flash | Gemini 3 Flash | Visual analysis |

### Custom (11)

| Agent | Model (Default) | Model (Cost-Efficient) | Dispatch when |
| :--- | :--- | :--- | :--- |
| **Navigator** | Gemini 3 Flash | Gemini 3 Flash | Browser automation, screenshots |
| **Detective** | GPT-5.4 Mini | DeepSeek V4 Flash | Production errors, logs, metrics |
| **Sage** | DeepSeek V4 Flash | DeepSeek V4 Flash | Gorgias metrics, schemas, rules |
| **Reviewer** | GPT-5.4 Mini | DeepSeek V4 Flash | PR/branch/diff review coordinator |
| **reviewer-code** | GPT-5.6 Terra | DeepSeek V4 Pro | CLAUDE.md compliance, bugs |
| **reviewer-errors** | GPT-5.6 Terra | DeepSeek V4 Pro | Silent failures, error handling |
| **reviewer-types** | GPT-5.6 Terra | DeepSeek V4 Pro | Type encapsulation, invariants |
| **reviewer-* (other)** | GPT-5.6 Luna/DeepSeek | DeepSeek V4 Flash | Specialized review lanes |

**Council** disabled. Observer auto-routes images from Orchestrator.

**Model Profiles Rationale:** The system defaults to a specialized mix of Gemini 3 Flash/Pro and GPT-5.6 models for complex reasoning. The `cost-efficient` profile swaps these for DeepSeek V4 (Flash/Pro) and Gemini 3 Flash, providing ~90-95% cost reduction with competitive performance for most routine development tasks.

## Directory Map

```
ai-rules/
├── openpackage.yml            # Manifest: declares rules, agents, skills, commands, MCP
├── opencode.jsonc             # Project-level OpenCode config (MCPs)
├── rules/                     # Rule files (distributed as prompt overrides)
│   ├── overview.md            # GitHub/git/PR rules
│   ├── custom-rules.md        # Workflow, packages, commits, dispatch rules
│   ├── git-remote-confirmation.md  # gh CLI + git safety
│   ├── pr-workflow.md         # PR creation workflow
│   ├── security-scan.md       # On-demand commit/push safety checklist
│   ├── rtk.md                 # RTK token optimization
│   ├── user-config.md         # Machine config, env vars, aliases
│   └── codebase-memory.md     # Codebase Memory MCP usage guide
├── agents/                    # Custom agent prompt definitions
│   ├── navigator.md           # Browser automation
│   ├── detective.md           # Production diagnostics
│   └── sage.md                # Gorgias domain knowledge
├── commands/
│   └── review-pr.md           # PR review command
├── skills/
│   └── project-context/       # Summarize project context
└── agents-overview/           # Interactive visualization (data.yaml + index.html)
```

## SDD Artifacts — `docs/.planning/`

Spec Driven Development artifacts live inside each working repo at `docs/.planning/`:

```
<repo>/docs/.planning/
├── specs/                          # Design docs (brainstorming phase)
│   └── YYYY-MM-DD-<topic>-design.md
├── plans/                          # Implementation plans (writing-plans phase)
│   └── YYYY-MM-DD-<feature>.md
├── ledger-<plan>.md                # Execution ledger (executing-plans phase)
└── reports/                        # Per-task implementer reports
    └── <plan>-task-<N>-report.md
```

### SDD Workflow (4-step)

| Phase | Skill | Key agents |
|---|---|---|
| 1. Brainstorm | `brainstorming` | @explorer, @librarian, @oracle, @designer |
| 2. Plan | `writing-plans` | — (orchestrator writes plan directly) |
| 3. Execute | `executing-plans` | @fixer (code), @designer (UI), @reviewer (per-task gate), @oracle (escalation) |
| 4. Review (optional; user-confirmed) | `reviewing-plans` | @reviewer (final gate — 7 reviewer-* specialists, only after opt-in) |

See `docs/sdd-workflow.md` for the full flowchart and agent usage matrix.

## Agent tmp paths

| Agent | Output path |
|-------|-------------|
| Navigator | `~/developer/.ai-work/tmp/navigator/` |
| Sage | `~/developer/.ai-work/tmp/sage/` |

> PR description files use `/tmp/pr-<branch>.md` (ephemeral, not grouped here).

## RTK — Token Optimization Plugin

RTK is installed as a real OpenCode plugin that transparently rewrites commands before execution. No manual prefixing needed.

```bash
# Install (already done — plugin at ~/.config/opencode/plugins/rtk.ts)
rtk init -g --opencode

# Verify
rtk --version
```

> **Note:** After installing the plugin, restart OpenCode. Test with `git status` — RTK rewrites it transparently.

## Configuration Layers

| Layer | File | What it controls |
|-------|------|-----------------|
| Provider + MCPs | `~/.config/opencode/opencode.json` | Bifrost models (`bf`, `bf-a`, `bf-o`), MCP server endpoints |
| OMO Slim plugin | `~/.config/opencode/opencode.jsonc` | Plugin registration, LSP, disabled default agents |
| Agent models + MCPs | `~/.config/opencode/oh-my-opencode-slim.json` | Preset `bifrost`, per-agent model/variant/skills/MCPs, custom agents, tmux |
| Prompt overrides | `~/.config/opencode/oh-my-opencode-slim/{agent}_append.md` | Per-agent appended instructions from rules/ |
| Global instructions | `~/.config/opencode/AGENTS.md` | OMO Slim managed |
| Project config | `<repo>/opencode.jsonc` | Project-level MCPs, model overrides |

## How to Update

### Change an agent's model

Edit `oh-my-opencode-slim.json` → update the `model` field under the `bifrost` preset.

### Add a rule

1. Create `rules/<name>.md`
2. Add its content to the relevant `{agent}_append.md` in `~/.config/opencode/oh-my-opencode-slim/`
3. Update `openpackage.yml` if needed

### Change a custom agent's prompt

Edit the corresponding `agents/<name>.md` file, then copy the body (after frontmatter) into the `prompt` field in `oh-my-opencode-slim.json`.

## MCP Inventory

All configured in `~/.config/opencode/opencode.json`:

| MCP | Enabled | Assigned to |
|-----|---------|------------|
| codebase-memory-mcp | ✓ | Orchestrator, Oracle, Explorer, Fixer, Detective, Sage |
| context7 | ✓ | Librarian |
| github | ✓ | Orchestrator |
| sentry | ✓ | Detective |
| linear | ✓ | Librarian |
| datadog | ❌ removed | Detective uses `pup` CLI via Bash instead |
| gcp-logging | ✓ | Detective |
| context-layer | ✓ | Sage |
| notion | ✓ | Librarian |
| rootly | ✓ | Detective |
| mcp-server-browser | ✓ | Navigator |
| gorgias-mcp | disabled | — |
| figma | ✓ | — |

**Datadog access:** via `pup` CLI (Bash), not MCP. Always call with `--agent --read-only` flags: `pup --agent --ro logs search ...`

## Provider: Bifrost

Models routed through `https://bifrost.ops.gorgias.io` with 3 provider types:

- `bf` — OpenAI-compatible (DeepSeek V4, Gemini, GLM)
- `bf-a` — Anthropic (Claude Haiku 4.5, Sonnet 4.6/5, Opus 4.8)
- `bf-o` — OpenAI (GPT-4o, GPT-5.x Terra/Luna/Sol)

Auth via `{file:/Users/guilhermebomfim/.config/gorgias-ai/bifrost-virtual-key}`.
