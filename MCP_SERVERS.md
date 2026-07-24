# MCP Servers

Central inventory of all MCP (Model Context Protocol) servers configured across LLM tools.

---

## Global MCPs (All Platforms via `codebase-memory-mcp`)

| Name | Type | Platforms | Purpose |
|------|------|-----------|---------|
| `codebase-memory-mcp` | stdio | Claude Code, Codex, Gemini, OpenCode, Antigravity, Zed, VS Code, Cursor | Local code-intelligence server — persistent knowledge graph over source for graph-based exploration |

### codebase-memory-mcp

Local, single-binary code-intelligence server ([DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)). Builds a persistent knowledge graph from source using tree-sitter (158 languages) plus semantic type resolution for 12 (Python, TypeScript, Go, Rust, Java, PHP, C#, C/C++, Kotlin). Sub-millisecond queries, ~99% fewer tokens than file-by-file reading, 100% local (no telemetry, code never leaves the machine).

Automatically installed and configured across all AI tools (Claude Code, Codex, Gemini CLI, OpenCode, Antigravity, Zed, VS Code, Cursor).

**Config:** `.rulesync/mcp.json` — `command: /Users/guilhermebomfim/.local/bin/codebase-memory-mcp`.

**Hooks:**
- Claude Code: `PreToolUse` hook (Grep/Glob search-graph augmenter, non-blocking)
- Other tools: `SessionStart` hook (MCP usage reminder)

**Tools (15):**
- Discover/search: `search_graph`, `search_code`, `get_architecture`
- Trace/read: `trace_path`, `get_code_snippet`, `query_graph` (read-only Cypher), `get_graph_schema`, `detect_changes`
- Manage: `index_repository`, `list_projects`, `index_status`, `delete_project`, `ingest_traces`, `manage_adr`

**Indexing modes:** `full` (files + similarity/semantic edges) · `moderate` · `fast` (no similarity/semantic) · `cross-repo-intelligence` (match Routes/Channels across projects). `persistence: true` writes a shareable `.codebase-memory/graph.db.zst`.

**Config files & env:** `.codebase-memory.json` (custom extensions), `.cbmignore` (ignore rules); `CBM_CACHE_DIR`, `CBM_WORKERS`, `CBM_ALLOWED_ROOT`, `CBM_LOG_LEVEL`.

**Use when:**
- Orienting in an unfamiliar codebase: `get_architecture`
- Finding a definition/symbol: `search_graph`, then `get_code_snippet`
- Callers/callees, impact, cross-service flow: `trace_path`
- Multi-hop / aggregate / hot-path queries: `query_graph`

**Agents with access:** `main`, `planner`, `observability-and-troubleshoot` (correlate telemetry to code), `cortex-agent` (map metrics/pipelines to implementation).

**Rule & skill:** `rules/codebase-memory.md` for full usage guidance; direct Cypher via `query_graph` for advanced graph operations.

---

## Claude Code (`~/.claude/settings.json`)

| Name | Type | Command | Purpose |
|------|------|---------|---------|
| `HomeAssistant` | stdio | `uvx ha-mcp@latest` | Control Home Assistant devices, automations, areas, entities |

### HomeAssistant

```json
{
  "command": "/opt/homebrew/bin/uvx",
  "args": ["--refresh", "ha-mcp@latest"],
  "env": {
    "HOMEASSISTANT_URL": "<set in settings.json>",
    "HOMEASSISTANT_TOKEN": "<set in settings.json>"
  }
}
```

**Use when:** Automating Home Assistant (lights, sensors, automations, etc.) via the HA skill (`/ha-api`).
**Env vars required:** `HOMEASSISTANT_URL`, `HOMEASSISTANT_TOKEN` (stored in `~/.claude/settings.json`).

### Claude Code Settings
Claude Code's `~/.claude/settings.json` also contains:

**Plugins (12 enabled):**
- `context7-mcp` — Up-to-date library docs
- `pr-review-toolkit` — PR review automation
- `frontend-design` — Frontend design assistance
- `code-review` — Code review assistance
- `github` — GitHub integration
- `warp` — Warp terminal integration
- `chrome-devtools-mcp` — Chrome DevTools integration
- `superpowers` — Superpowers (brainstorming, planning)
- `shopify-ai-toolkit` — Shopify development tools
- `claude-md-management` — CLAUDE.md management
- `superpowers-developing-for-claude-code` — Superpowers dev tools

**Model settings:** Sonnet (default), `ANTHROPIC_BASE_URL` proxied through Bifrost.
**Permissions:** Default `auto` mode with allowed commands for `gh pr`, `git`, `pnpm`, `ls`, `source`.

---

## Rulesync / Project-level MCPs (`.rulesync/mcp.json`)

These MCPs are defined in the rules repo and can be distributed to all tools via rulesync.

| Name | Type | Command | Purpose |
|------|------|---------|---------|
| `serena` | stdio | `uvx serena start-mcp-server` | Code intelligence / semantic search for current project |
| `context7` | stdio | `npx @upstash/context7-mcp` | Up-to-date library documentation lookup |

### serena

```json
{
  "type": "stdio",
  "command": "uvx",
  "args": [
    "--from", "git+https://github.com/oraios/serena",
    "serena", "start-mcp-server",
    "--context", "ide-assistant",
    "--enable-web-dashboard", "false",
    "--project", "."
  ]
}
```

**Use when:** Searching, navigating, or understanding code in the current project. Provides semantic code awareness beyond simple grep.

### context7

```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@upstash/context7-mcp"]
}
```

**Use when:** Looking up current documentation for any library or framework (React, Next.js, Prisma, etc.). More reliable than training data for recent versions.

---

## OpenCode

OpenCode has two config layers:
- **User-level:** `~/.config/opencode/opencode.jsonc` — Shell, MCPs (Sentry remote), AGENTS.md
- **Project-level:** `opencode.jsonc` (in project root) — Instructions referencing `.opencode/memories/`

### User-level MCPs (`~/.config/opencode/opencode.jsonc`)
| Name | Type | URL | Purpose |
|------|------|-----|---------|
| `sentry` | remote | `https://mcp.sentry.dev/mcp` | Sentry error monitoring and debugging |

### Project-level config
The rules repo's `opencode.jsonc` references instructions from `.opencode/memories/`:
```json
{
  "instructions": [
    ".opencode/memories/custom-rules.md",
    ".opencode/memories/security-scan.md",
    ".opencode/memories/user-config.md"
  ]
}
```

These memory files are generated by rulesync from `.rulesync/rules/`.

---

## Adding a New MCP

### To Claude Code globally
Edit `~/.claude/settings.json`, add entry under `mcpServers`.

### To all tools via rulesync
Edit `.rulesync/mcp.json`, add entry under `mcpServers`, then run rulesync.

### To OpenCode only
Edit `opencode.jsonc` in the project root.

---

## MCP Quick Reference

| Tool | Config Location | Scope |
|------|----------------|-------|
| Claude Code | `~/.claude/settings.json` | Global (all projects) |
| Rulesync | `.rulesync/mcp.json` | Per-project, distributed |
| OpenCode | `opencode.jsonc` | Per-project |
| Codex | `~/.codex/` | Per-session |
