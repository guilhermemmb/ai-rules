# ai-rules — OpenCode Agent Configuration

Source of truth for OpenCode agent rules, custom agents, skills, and commands. Used by [Oh My OpenCode Slim](https://ohmyopencodeslim.com/) with [Bifrost](https://bifrost.ops.gorgias.io) model routing.

## Quick Start

```bash
# Install OMO Slim with tmux
bunx oh-my-opencode-slim@latest install --tmux=yes

# Inside OpenCode
ping all agents
```

## Agent Pantheon

### Built-in (7 — OMO Slim)

| Agent | Model (Bifrost) | Role | MCPs |
|-------|----------------|------|------|
| **Orchestrator** | GPT-5.6 Terra (high) | Master delegator & coordinator | `*`, `!context7` |
| **Oracle** | GPT-5.6 Terra (high) | Strategic advisor, architecture, hard debugging | codebase-memory-mcp · skill: `simplify` |
| **Explorer** | DeepSeek V4 Flash (low) | Codebase reconnaissance | codebase-memory-mcp |
| **Librarian** | DeepSeek V4 Flash (low) | Knowledge retrieval | websearch, context7, gh_grep, linear, notion |
| **Designer** | Gemini 3 Pro Preview (medium) | UI/UX excellence | — |
| **Fixer** | GPT-5.6 Luna (xhigh) | Implementation specialist | codebase-memory-mcp |
| **Observer** | Gemini 3 Flash Preview | Visual analysis (images, PDFs) | — |

### Custom (11)

| Agent | Model (Bifrost) | MCPs | Dispatch when |
|-------|----------------|------|---------------|
| **Navigator** | Gemini 3 Flash Preview | mcp-server-browser | Navigation, screenshots, DOM, form fills, UI automation |
| **Detective** | GPT-5.4 Mini (high) | sentry, gcp-logging, rootly + **pup CLI** (Datadog) | Production errors, logs, metrics, traces, incidents |
| **Sage** | DeepSeek V4 Flash (low) | cortex, codebase-memory-mcp | Gorgias metrics, schemas, business rules, BigQuery, Notion docs |
| **Reviewer** | GPT-5.4 Mini (high) | github, codebase-memory-mcp | PR/branch/diff review — dispatches 7 `reviewer-*` specialists |
| **reviewer-code** | GPT-5.6 Terra (high) | codebase-memory-mcp, github | CLAUDE.md compliance, bugs, style (≥80 confidence) |
| **reviewer-comments** | DeepSeek V4 Flash (low) | codebase-memory-mcp, github | Comment accuracy, rot, completeness |
| **reviewer-test** | GPT-5.6 Luna (high) | codebase-memory-mcp, github | Behavioral test coverage, critical gaps |
| **reviewer-errors** | GPT-5.6 Terra (high) | codebase-memory-mcp, github | Silent failures, catch blocks, error handling |
| **reviewer-types** | GPT-5.6 Terra (high) | codebase-memory-mcp, github | Type encapsulation, invariant design |
| **reviewer-simplifier** | GPT-5.6 Luna (high) | codebase-memory-mcp | Code clarity, nesting reduction |
| **reviewer-accessibility** | GPT-5.6 Luna (high) | codebase-memory-mcp, github | WCAG 2.2 AA, contrast, keyboard, ARIA |

**Council** disabled. Observer auto-routes images from Orchestrator (GPT-5.6 Terra is not multimodal in this harness).

**Model mix rationale:** GPT-5.6 Terra is the precision-critical, low-volume tier for Oracle's strategic architecture and debugging work, the Orchestrator, and reviewer-code, reviewer-errors, and reviewer-types' formal invariant reasoning. GPT-5.6 Luna is the core high-volume workhorse covering fixer plus three reviewer specialists (test, simplifier, accessibility); GPT-5.4 Mini covers lighter-reasoning coordination (detective, reviewer). Gemini 3 Pro/Flash is reserved for genuine multimodal needs only (designer's Figma work; observer/navigator's screenshots). DeepSeek Flash handles cheap high-frequency or low-stakes text-only tasks (explorer, librarian, sage, reviewer-comments).

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
| 4. Review | `reviewing-plans` | @reviewer (final gate — 7 reviewer-* specialists) |

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
