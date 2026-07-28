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
| **Orchestrator** | GPT-5.6 Terra (xhigh) | Master delegator & coordinator | `*`, `!context7` |
| **Oracle** | GPT-5.4 (high) | Strategic advisor, architecture, hard debugging | codebase-memory-mcp · skill: `simplify` |
| **Explorer** | DeepSeek V4 Flash (low) | Codebase reconnaissance | codebase-memory-mcp |
| **Librarian** | DeepSeek V4 Flash (low) | Knowledge retrieval | websearch, context7, gh_grep, linear, notion |
| **Designer** | GPT-5.6 Sol (medium) | UI/UX excellence | — |
| **Fixer** | GPT-5.4 (xhigh) | Implementation specialist | codebase-memory-mcp |
| **Observer** | Gemini 3 Flash Preview | Visual analysis (images, PDFs) | — |

### Custom (3)

| Agent | Model (Bifrost) | MCPs | Dispatch when |
|-------|----------------|------|---------------|
| **Navigator** | Gemini 3 Flash Preview | mcp-server-browser | Navigation, screenshots, DOM, form fills, UI automation |
| **Detective** | GPT-5.4 | sentry, gcp-logging, rootly + **pup CLI** (Datadog) | Production errors, logs, metrics, traces, incidents |
| **Sage** | GPT-4o-mini | context-layer | Gorgias metrics, schemas, business rules, BigQuery |

**Council** disabled. Observer auto-routes images from Orchestrator (DeepSeek V4 is not multimodal).

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

## Working Directory — `~/.ai-work`

All AI agent working files are grouped under `~/developer/.ai-work/` — outside any repo, never committed.

```
~/developer/.ai-work/
├── openspec/              # OpenSpec plans & specs, one subfolder per repo
│   └── gorgias-chat/      # plans, specs/, design.md, tasks.md for gorgias-chat
└── tmp/                   # Agent scratch output
    ├── navigator/          # Navigator browser extraction results
    └── sage/               # Sage domain knowledge query results
```

### OpenSpec stores

Each repo's plans live at `~/developer/.ai-work/openspec/<repo>/`. To register a new repo:

```bash
openspec store setup <repo> --path ~/developer/.ai-work/openspec/<repo> --no-init-git
```

List registered stores:

```bash
openspec store list --json
```

### Agent tmp paths

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
- `bf-a` — Anthropic (Claude Haiku/Sonnet/Opus)
- `bf-o` — OpenAI (GPT-4o, GPT-5.x Terra/Luna/Sol)

Auth via `{file:/Users/guilhermebomfim/.config/gorgias-ai/bifrost-virtual-key}`.
