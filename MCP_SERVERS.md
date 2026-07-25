# MCP Servers

Central inventory of all MCP servers configured in `~/.claude/settings.json`.

---

## Agent Assignment

| MCP | Agent(s) with access |
|-----|---------------------|
| `codebase-memory-mcp` | all agents |
| `context7-mcp` | main |
| `context-mode` | all agents |
| `github` | main |
| `mcp-server-browser` | browser-agent |
| `chrome-devtools-mcp` | browser-agent |
| `sentry-mcp` | observability-and-troubleshoot |
| `gcloud` | observability-and-troubleshoot |
| `gcloud-observability-ai-agent` | observability-and-troubleshoot |
| `gcloud-observability-chat` | observability-and-troubleshoot |
| `cortex` | cortex-agent |
| `linear` | knowledge-agent |
| `notion` | knowledge-agent |

---

## Servers

### codebase-memory-mcp

Local code-intelligence server. Builds a persistent knowledge graph from source using tree-sitter (158 languages). Sub-millisecond queries, ~99% fewer tokens than file-by-file reading, 100% local.

```json
{
  "command": "npx",
  "args": ["-y", "codebase-memory-mcp"]
}
```

**Tools:** `search_graph`, `search_code`, `get_architecture`, `trace_path`, `get_code_snippet`, `query_graph`, `get_graph_schema`, `detect_changes`, `index_repository`, `list_projects`, `index_status`, `delete_project`, `ingest_traces`, `manage_adr`

**Rule:** `rules/codebase-memory.md`

---

### context-mode

Token-optimized context compression. Intercepts tool calls, filters and compresses output to reduce token usage 60–90%. Provides SQLite FTS5-backed session history. Available to all agents.

```json
{
  "command": "context-mode"
}
```

**Diagnostic commands:** `/context-mode:ctx-doctor` (health check) · `/context-mode:ctx-stats` (token savings breakdown)

---

### context7-mcp

Up-to-date library documentation lookup via HTTP. Fetches current docs for any library or framework — more reliable than training data for recent versions.

```json
{
  "type": "http",
  "url": "https://mcp.context7.com/mcp"
}
```

**Rule:** `rules/context7.md`

---

### github

GitHub CLI integration. Exposes `gh` commands as MCP tools for PR, issue, and repo operations.

```json
{
  "command": "gh",
  "args": []
}
```

---

### mcp-server-browser

Primary browser automation. Used by `browser-agent` for all navigation, interaction, screenshot, and content extraction tasks.

```json
{
  "command": "npx",
  "args": ["@agent-infra/mcp-server-browser@latest"]
}
```

**Tools:** `browser_navigate`, `browser_screenshot`, `browser_click`, `browser_form_input_fill`, `browser_get_text`, `browser_get_markdown`, `browser_scroll`, `browser_evaluate`, and more. See `subagents/browser-agent.md` for full tool list.

---

### chrome-devtools-mcp

Chrome DevTools integration. Used by `browser-agent` for heavy inspection — performance profiling, Lighthouse audits, network analysis. Not for general navigation.

```json
{
  "command": "npx",
  "args": ["-y", "chrome-devtools-mcp@latest", "--no-usage-statistics"]
}
```

---

### sentry-mcp

Sentry error monitoring. Read-only access to issues, events, stack traces. Used by `observability-and-troubleshoot` only.

```json
{
  "command": "npx",
  "args": ["-y", "@sentry/mcp-server@latest", "--agent"],
  "env": {"SENTRY_ACCESS_TOKEN": "${SENTRY_ACCESS_TOKEN}"}
}
```

---

### gcloud

GCP Cloud Logging CLI via MCP. Always used together with `gcloud-observability-ai-agent` and `gcloud-observability-chat`. Used by `observability-and-troubleshoot` only.

```json
{
  "command": "npx",
  "args": ["-y", "@google-cloud/gcloud-mcp"]
}
```

---

### gcloud-observability-ai-agent

GCP Observability MCP scoped to `gorgias-conversations-prod`. Always paired with `gcloud` — both go to `observability-and-troubleshoot`.

```json
{
  "command": "npx",
  "args": ["-y", "@google-cloud/observability-mcp", "--project", "gorgias-conversations-prod"]
}
```

---

### gcloud-observability-chat

GCP Observability MCP scoped to `gorgias-chat-production`. Always paired with `gcloud` — both go to `observability-and-troubleshoot`.

```json
{
  "command": "npx",
  "args": ["-y", "@google-cloud/observability-mcp", "--project", "gorgias-chat-production"]
}
```

---

### cortex

Gorgias Context Layer MCP. Exposes metric definitions, table schemas, business rules, and BigQuery data. Used by `cortex-agent` only.

```json
{
  "type": "http",
  "url": "https://cortex.mcp.gorgias-decision-engine.com/mcp"
}
```

---

### linear

Linear issue tracking. Read-only access to issues, epics, cycles, and projects. Used by `knowledge-agent` only.

```json
{
  "command": "npx",
  "args": ["-y", "@linear/sdk-mcp"],
  "env": {"LINEAR_API_KEY": "${LINEAR_API_KEY}"}
}
```

---

### notion

Notion knowledge base. Read-only access to pages, databases, and docs. Used by `knowledge-agent` only.

```json
{
  "command": "npx",
  "args": ["-y", "@notion-mcp/notion-mcp"]
}
```

---

## Rulesync / Project-level MCPs (`.rulesync/mcp.json`)

Distributed to all AI tools (Codex, OpenCode, Gemini, etc.) via rulesync. Subset of the Claude Code mcpServers above.

| Name | Purpose |
|------|---------|
| `context7-mcp` | Library docs (stdio/npx variant for tools without http MCP support) |
| `codebase-memory-mcp` | Code intelligence graph |

---

## Adding a New MCP

**Claude Code only:** Add entry under `mcpServers` in `~/.claude/settings.json`, then add it to the relevant subagent's `mcpServers` frontmatter array in `.rulesync/subagents/`.

**All tools via rulesync:** Add to `.rulesync/mcp.json` under `mcpServers`, then run `rulesync`.

---

## Quick Reference

| Config location | Scope |
|----------------|-------|
| `~/.claude/settings.json` | Claude Code global |
| `.rulesync/mcp.json` | All tools via rulesync |
| `.rulesync/subagents/*.md` frontmatter | Per-agent access control |
