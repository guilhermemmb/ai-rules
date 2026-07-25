# bridgetown — AI Rules Engine

Single source of truth for all LLM tool configurations. Change rules, agents, or skills here; rulesync distributes them everywhere.

## What this is

All LLM configs are authored here and distributed to Claude Code, OpenCode, Codex, Warp, and Zed. Previously scattered across `~/.ai-agents/`, `~/.claude/`, `~/.codex/`. Now: change once, push everywhere.

## Directory Map

```
bridgetown/
├── CLAUDE.md                  # Master instructions for Claude Code (always loaded)
├── AGENTS.md                  # Auto-generated via build-agents.sh — gitignored
├── ARCHITECTURE.md            # Full architecture narrative
├── DEPLOY.md                  # How to deploy agent tool/MCP configs
├── RULES_GUIDE.md             # How rules are organized and when loaded
├── MCP_SERVERS.md             # MCP inventory across all tools
├── rulesync.jsonc             # rulesync targets and features config
├── opencode.jsonc             # OpenCode project-level config
├── build-agents.sh            # Generates per-agent tool/MCP JSON config
├── merge-rules.sh             # Builds AGENTS.md from AGENTS.source.md + rules
├── agents/                    # Agent definitions (parsed by build-agents.sh)
│   ├── main.md                # Orchestrator: code, planning, dispatch
│   ├── browser-agent.md       # mcp-server-browser (tier 1) + chrome-devtools-mcp (tier 2)
│   ├── observability-and-troubleshoot.md  # Sentry + Datadog + GCP
│   ├── cortex-agent.md        # Cortex MCP (Gorgias domain knowledge)
│   ├── knowledge-agent.md     # Notion + Linear MCPs
│   ├── routing.md             # Dispatch rules & examples
│   └── README.md              # Quick agent reference
└── .rulesync/                 # Source of truth — distributed by rulesync
    ├── rules/                 # → ~/.claude/rules/, .opencode/, .codex/, .warp/
    ├── skills/                # → ~/.claude/skills/
    ├── commands/              # → ~/.claude/commands/
    ├── subagents/             # → ~/.claude/agents/
    ├── mcp.json               # MCP servers for rulesync targets
    └── hooks.json             # Tool-use hooks
```

## How Rules Flow

```
.rulesync/rules/*.md  ──rulesync──►  ~/.claude/rules/*.md        (Claude Code)
                                  ──►  ~/.opencode/memories/*.md  (OpenCode)
                                  ──►  ~/.codex/instructions/*.md  (Codex)
                                  ──►  ~/.warp/ai-instructions/*.md (Warp)
```

`rulesync.jsonc` at the repo root controls targets and features. Run `rulesync` after any change to `.rulesync/`.

> **All rules must live in `.rulesync/rules/`** — this is the single source of truth. Do not create a top-level `rules/` directory; files there are not distributed by rulesync and will be ignored.

## Agent System

Main agent orchestrates; it cannot directly touch browser, observability, or domain-knowledge tools — it dispatches to the appropriate subagent.

| Agent | Purpose | MCPs | Dispatch When |
|-------|---------|------|---------------|
| **main** | Orchestrator | codebase-memory-mcp, github, context7-mcp | Code, planning, implementation |
| **browser-agent** | Browser interaction | mcp-server-browser, chrome-devtools-mcp | Navigation, screenshots, DOM, web automation |
| **observability-and-troubleshoot** | Production diagnostics | sentry-mcp, datadog-mcp, gcloud, gcloud-observability | Errors, logs, metrics, root cause |
| **cortex-agent** | Gorgias domain knowledge | cortex | Metrics, schemas, business rules |
| **knowledge-agent** | Internal docs & issues | notion, linear | Notion pages, Linear issues/specs |

See `agents/routing.md` for dispatch rules and examples.

### Tool Isolation

`build-agents.sh` parses each `agents/*.md` frontmatter and generates a JSON config listing allowed tools and MCPs per agent. Apply the output to `~/.claude/settings.json` (see `DEPLOY.md`). Until applied, MCPs are accessible to all agents.

### GCP Logging Pattern

GCP logging: CLI first, MCP fallback.

1. Try `gcloud logging read` CLI (always available, token-efficient)
2. Fall back to GCP Cloud Logging MCP when CLI is unavailable or insufficient

## How to Add Things

### New rule
1. Create `.rulesync/rules/foo.md` with frontmatter (`name`, `description`, `metadata.type: rule`)
2. Run `rulesync`

### New skill
1. Create `.rulesync/skills/foo/SKILL.md`
2. Run `rulesync`

### New agent
1. Create `agents/foo.md` — frontmatter defines `name`, `tools`, `mcps`, `constraints`
2. Create `.rulesync/subagents/foo.md` — full agent definition distributed to `~/.claude/agents/`
3. Run `rulesync`, then run `./build-agents.sh` and apply output

### New MCP (all tools)
1. Add to `.rulesync/mcp.json`
2. Run `rulesync`

### New MCP (Claude Code only)
Add directly to `~/.claude/settings.json` under `mcpServers`.

### New command
1. Create `.rulesync/commands/foo.md`
2. Run `rulesync`

## Deployment

```bash
# Generate agent tool/MCP config
./deploy.sh

# Sync agents to settings only (fast)
./deploy.sh --sync-agents
```

See `DEPLOY.md` for full steps including dry-run verification.

## First-Time Setup

**Add SessionStart hook to `~/.claude/settings.json`:**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "cd /Users/guilhermebomfim/developer/dotfiles/ai-rules && ./deploy.sh --sync-agents --quiet"
          }
        ]
      }
    ]
  }
}
```

This auto-syncs agent config (tools/MCPs) from `agents/main.md` and subagents every Claude Code startup. Ensures main agent stays restricted to `[codebase-memory-mcp, github, context7-mcp]`, dropping MCP token load from ~70k to ~30-40k.

## Global MCP Server Setup

Global `~/.claude/settings.json` defines mcpServers and disables plugin-based MCPs to reduce token load:

**mcpServers configured:**

```json
{
  "mcpServers": {
    "codebase-memory-mcp": {"command": "npx", "args": ["-y", "codebase-memory-mcp"]},
    "context7-mcp": {"type": "http", "url": "https://mcp.context7.com/mcp"},
    "github": {"command": "gh", "args": []},
    "mcp-server-browser": {"command": "npx", "args": ["@agent-infra/mcp-server-browser@latest"]},
    "chrome-devtools-mcp": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest", "--no-usage-statistics"]},
    "sentry-mcp": {"command": "npx", "args": ["-y", "@sentry/mcp-server@latest", "--agent"]},
    "datadog-mcp": {"command": "/opt/homebrew/bin/pup", "args": ["mcp", "--agent", "--read-only"]},
    "cortex": {"type": "http", "url": "https://cortex.mcp.gorgias-decision-engine.com/mcp"},
    "linear": {"command": "npx", "args": ["-y", "@linear/sdk-mcp"]},
    "notion": {"command": "npx", "args": ["-y", "@notion-mcp/notion-mcp"]},
    "gcloud": {"command": "npx", "args": ["-y", "@google-cloud/gcloud-mcp"]},
    "gcloud-observability": {"command": "npx", "args": ["-y", "@google-cloud/observability-mcp"]},
    "HomeAssistant": {"command": "/opt/homebrew/bin/uvx", "args": ["--refresh", "ha-mcp@latest"]}
  }
}
```

**MCP plugins disabled in enabledPlugins** (replaced by mcpServers entries above):

- `context7-mcp@claude-plugins-official`
- `chrome-devtools-mcp@chrome-devtools-plugins`
- `sentry-cli@claude-plugins-official`

**Non-MCP utility plugins kept enabled:**

- caveman, code-review, pr-review-toolkit, claude-md-management, skill-creator, code-simplifier, superpowers, superpowers-developing-for-claude-code

MCPs load on-demand via npx instead of pre-loading as plugins. Reduces token overhead for sessions outside ai-rules.

## Key Files Reference

| File | Loaded when | Tool |
|------|------------|------|
| `CLAUDE.md` | Always | Claude Code |
| `AGENTS.md` (auto-generated) | Always | Codex, Gemini |
| `~/.claude/rules/*.md` | Always (via UserPromptSubmit hook) | Claude Code |
| `~/.claude/agents/*.md` | When subagent spawned | Claude Code |
| `~/.claude/skills/*/SKILL.md` | On `/skill-name` invocation | Claude Code |
| `~/.claude/commands/*.md` | On `/command-name` invocation | Claude Code |
