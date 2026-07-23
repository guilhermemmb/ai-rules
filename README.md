# bridgetown — AI Rules Engine

Single source of truth for all LLM tool configurations. Change rules, agents, or skills here; rulesync distributes them everywhere.

## What this is

All LLM configs are authored here and distributed to Claude Code, OpenCode, Codex, Warp, and Zed. Previously scattered across `~/.ai-agents/`, `~/.claude/`, `~/.codex/`. Now: change once, push everywhere.

## Directory Map

```
bridgetown/
├── CLAUDE.md                  # Master instructions for Claude Code (always loaded)
├── AGENTS.source.md           # Hand-authored source for AGENTS.md (Codex/Gemini)
├── AGENTS.md                  # Auto-generated via merge-rules.sh — gitignored
├── ARCHITECTURE.md            # Full architecture narrative
├── DEPLOY.md                  # How to deploy agent tool/MCP configs
├── RULES_GUIDE.md             # How rules are organized and when loaded
├── MCP_SERVERS.md             # MCP inventory across all tools
├── AGENT_ROUTING.md           # Decision guide: which agent/skill for which task
├── rulesync.jsonc             # rulesync targets and features config
├── opencode.jsonc             # OpenCode project-level config
├── build-agents.sh            # Generates per-agent tool/MCP JSON config
├── merge-rules.sh             # Builds AGENTS.md from AGENTS.source.md + rules
├── agents/                    # Agent definitions (parsed by build-agents.sh)
│   ├── main.md                # Orchestrator: code, planning, dispatch
│   ├── browser-agent.md       # Chrome DevTools + superpowers-chrome
│   ├── observability-and-troubleshoot.md  # Sentry + Datadog + GCP
│   ├── cortex-agent.md        # Cortex MCP (Gorgias domain knowledge)
│   ├── knowledge-agent.md     # Notion + Linear MCPs
│   ├── routing.md             # Dispatch rules & examples
│   └── README.md              # Quick agent reference
├── rules/                     # Always-on supplementary rules (not in .rulesync)
│   ├── git-remote-confirmation.md
│   └── pr-workflow.md
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

## Agent System

Main agent orchestrates; it cannot directly touch browser, observability, or domain-knowledge tools — it dispatches to the appropriate subagent.

| Agent | Purpose | MCPs | Dispatch When |
|-------|---------|------|---------------|
| **main** | Orchestrator | codebase-memory-mcp, github, context7 | Code, planning, implementation |
| **browser-agent** | Browser interaction | chrome-devtools, superpowers-chrome | Screenshots, DOM, web automation |
| **observability-and-troubleshoot** | Production diagnostics | sentry, datadog, gcloud | Errors, logs, metrics, root cause |
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
./build-agents.sh /tmp/agents-config.json

# Review output
cat /tmp/agents-config.json | jq .

# Apply to settings (merge into agents section of ~/.claude/settings.json)
```

See `DEPLOY.md` for full steps including dry-run verification.

## Key Files Reference

| File | Loaded when | Tool |
|------|------------|------|
| `CLAUDE.md` | Always | Claude Code |
| `AGENTS.md` (merged) | Always | Codex, Gemini |
| `~/.claude/rules/*.md` | Always (via UserPromptSubmit hook) | Claude Code |
| `~/.claude/agents/*.md` | When subagent spawned | Claude Code |
| `~/.claude/skills/*/SKILL.md` | On `/skill-name` invocation | Claude Code |
| `~/.claude/commands/*.md` | On `/command-name` invocation | Claude Code |
