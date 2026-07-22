# Architecture: Rules Repo

This repo is the **single source of truth** for all LLM tool configurations. Instructions, skills, agents, commands, and MCP servers are defined here and distributed to every tool via symlinks and rulesync.

---

## Why This Repo Exists

Previously, configurations were scattered across `~/.ai-agents/`, `~/.claude/`, `~/.codex/`, etc. Changes had to be made in multiple places, symlinks pointed everywhere, and it was impossible to know what was authoritative. This repo centralizes everything.

**Rule:** If you change an instruction, skill, or agent — change it here. Everywhere else is either a symlink or a rulesync output.

---

## Directory Structure

```
rules/
├── CLAUDE.md                    # Main instructions for all LLMs (source of truth)
├── AGENTS.md                    # Agent definitions for Codex / OpenCode / Antigravity
├── ARCHITECTURE.md              # This file
├── MCP_SERVERS.md               # Inventory of all MCP servers
├── RULES_GUIDE.md               # How rules are organized and how to update them
├── AGENT_ROUTING.md             # Decision tree: which agent to use and when
├── opencode.jsonc               # OpenCode project config (MCPs, model, etc.)
├── rulesync.jsonc               # Rulesync distribution targets and features
├── .rules                       # Rules in alternative format (Cursor, etc.)
│
├── .agents/                     # Shared config consumed by all tools via symlinks
│   ├── skills/                  # ← ALL tools symlink their skills/ here
│   │   ├── agent-browser-gorgias/
│   │   ├── gh-stack/
│   │   ├── ha-api/
│   │   ├── project-context/
│   │   └── react-doctor/
│   ├── agents/                  # Agent definitions
│   │   ├── planner.md
│   │   └── planner.toml
│   └── commands/                # Slash commands
│       └── review-pr.md
│
├── .rulesync/                   # Rulesync source files (distributed on sync)
│   ├── rules/                   # Per-domain rule files
│   │   ├── overview.md          # Global instructions (root: true)
│   │   ├── custom-rules.md      # Always-applied workflow rules
│   │   ├── security-scan.md     # On-demand security checklist
│   │   └── user-config.md       # Machine / env configuration
│   ├── subagents/
│   │   └── planner.md
│   ├── commands/
│   │   └── review-pr.md
│   ├── skills/
│   │   └── project-context/
│   ├── mcp.json                 # MCP servers for distribution
│   ├── hooks.json               # Post-tool-use hooks
│   └── .aiignore
│
├── .claude/                     # Claude Code specific (rulesync output)
│   ├── rules/
│   │   ├── custom-rules.md
│   │   ├── security-scan.md
│   │   └── user-config.md
│   ├── agents/
│   ├── commands/
│   └── skills/                  # Symlink → .agents/skills/
│
├── .opencode/                   # OpenCode specific (rulesync output)
│   ├── memories/
│   │   ├── custom-rules.md
│   │   ├── security-scan.md
│   │   └── user-config.md
│   ├── agents/
│   ├── commands/
│   └── skills/                  # Symlink → .agents/skills/
│
├── .warp/                       # Warp specific (rulesync output)
│   └── skills/                  # Symlink → .agents/skills/
│
└── .codex/                      # Codex specific (rulesync output)
    └── skills/                  # Symlink → .agents/skills/
```

---

## Symlink Map

Every tool's skills directory points to the same place:

| Symlink | Points To |
|---------|-----------|
| `~/.claude/skills` | `/developer/rules/.agents/skills` |
| `~/.agents/skills` | `/developer/rules/.agents/skills` |
| `~/.ai-agents/skills` | `/developer/rules/.agents/skills` |
| `~/.ai-agents/INSTRUCTIONS.md` | `/developer/rules/CLAUDE.md` |
| `~/.codex/AGENTS.md` | `/developer/rules/AGENTS.md` |
| `~/.claude/hooks/caveman-session-guidance` | `/developer/rules/.claude/hooks/caveman-session-guidance` |
| `.opencode/skills/` | `../.agents/skills` |
| `.warp/skills/` | `../.agents/skills` |

---

## How Rules Are Distributed

1. **Edit** in `.rulesync/rules/` (or `CLAUDE.md` for global instructions)
2. **Run rulesync** — it writes to `.claude/`, `.opencode/`, `.warp/`, `.codex/`, `AGENTS.md`
3. **Symlinks** ensure tools like Claude Code pick up skill/agent changes immediately

### Rulesync Targets

Configured in `rulesync.jsonc`:
- `claudecode` → `.claude/`
- `codexcli` → `.codex/` (and `AGENTS.md`)
- `opencode` → `.opencode/`
- `zed` → `.zed/`
- `warp` → `.warp/`

### Rulesync Features

- `rules` — Context rules loaded by tools
- `commands` — Slash commands (`/review-pr`, etc.)
- `subagents` — Custom agent definitions
- `skills` — Shareable skills

---

## Skills

Skills live in `.agents/skills/<skill-name>/` and require a `SKILL.md` file.

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `agent-browser-gorgias` | `/agent-browser-gorgias` | Persistent browser profile for Gorgias logins |
| `gh-stack` | `/gh-stack` | Manage stacked PRs with `gh stack` |
| `ha-api` | `/ha-api` | Home Assistant JS API client reference |
| `project-context` | `/project-context` | Summarize current project context |
| `react-doctor` | `/react-doctor` | Scan React codebase for issues (0–100 score) |

See `RULES_GUIDE.md` for how to add a new skill.

---

## Agents

Agents live in `.agents/agents/`. Each is a specialized LLM persona for a specific type of task.

| Agent | File | Purpose |
|-------|------|---------|
| `planner` | `planner.md` / `planner.toml` | Read-only planning agent — analyzes code and produces implementation plans without writing code |

See `AGENT_ROUTING.md` for when to use each agent.

---

## MCP Servers

See `MCP_SERVERS.md` for the full inventory.

Quick summary:
- **HomeAssistant** — Global (Claude Code `~/.claude/settings.json`)
- **serena** — Per-project (`.rulesync/mcp.json`)
- **context7** — Per-project (`.rulesync/mcp.json`)

---

## How to Add / Update Things

### New skill
1. Create `.agents/skills/<name>/SKILL.md`
2. Optionally add to `.rulesync/skills/<name>/SKILL.md` for rulesync distribution
3. Run rulesync if needed

### New agent
1. Add `.agents/agents/<name>.md`
2. Mirror in `.rulesync/subagents/<name>.md`
3. Run rulesync

### New slash command
1. Add `.agents/commands/<name>.md`
2. Mirror in `.rulesync/commands/<name>.md`
3. Run rulesync

### New MCP server (global)
1. Edit `~/.claude/settings.json`
2. Document in `MCP_SERVERS.md`

### New MCP server (per-project)
1. Edit `.rulesync/mcp.json`
2. Document in `MCP_SERVERS.md`
3. Run rulesync

### Update instructions
1. Edit `CLAUDE.md` for global changes
2. For domain-specific rules, edit the relevant file in `.rulesync/rules/`
3. Run rulesync to distribute

---

## OpenCode Notes

OpenCode has two configuration layers:

### User-level (`~/.config/opencode/`)
- `opencode.jsonc` — Shell (`zsh`), MCP servers (Sentry remote), model settings
- `AGENTS.md` — Global instructions (matches `rules/CLAUDE.md` content)
- `agents/` — Custom agent definitions
- `commands/` — Slash commands
- `skills/` — Symlink to managed skills

### Project-level (`rules/.opencode/`)
- `opencode.jsonc` — Model, MCPs, provider settings
- `memories/` — Always-applied context (generated by rulesync from `.rulesync/rules/`)
- `agents/` — Custom agents (generated by rulesync)
- `commands/` — Slash commands (generated by rulesync)
- `skills/` → symlink to `.agents/skills/`
