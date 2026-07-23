# Agent Configuration

Granular agent definitions with tool/MCP restrictions for ai-rules/bridgetown.

## Structure

- **main.md** — Orchestrator. Reads code, plans, dispatches work. Core tools: Bash, Read, Edit, Write, Agent
- **browser-agent.md** — Browser interaction specialist. Tools: chrome-devtools, superpowers-chrome MCPs
- **observability-and-troubleshoot.md** — Production troubleshooter. Tools: Sentry, Datadog pup, gcloud logging
- **cortex-agent.md** — Gorgias domain knowledge specialist. Tools: cortex MCP
- **knowledge-agent.md** — External knowledge reader. Tools: Notion, Linear (MCPs)
- **routing.md** — Dispatch rules. When to use each agent (examples included)

## Quick Reference

| Task | Agent | Why |
|------|-------|-----|
| Code exploration, implementation | main | Core read/write access |
| Take screenshot, fill form, click button | browser-agent | Elevated chrome-devtools |
| Find Sentry errors, query logs, diagnose issue | observability-and-troubleshoot | Elevated Sentry/Datadog/gcloud |
| Gorgias metrics, schemas, business rules | cortex-agent | Elevated cortex MCP |
| Notion docs, Linear issues, specs | knowledge-agent | Elevated Notion/Linear MCPs |
| Design refactor, architecture decision | planner | Specialized planning |

## Tool Access Levels

**Main (Full Context):**
- Bash, Read, Edit, Write, Glob, Agent, Task*
- MCPs: codebase-memory-mcp, github, context7
- **No access to:** cortex, Notion, Linear, chrome-devtools, Sentry

**Browser Agent (Restricted):**
- Bash (limited), Write
- MCPs: chrome-devtools, superpowers-chrome
- Output: /tmp/browser-agent/ only, JSON schema

**Observability (Restricted):**
- Bash (pup with --agent --read-only, gcloud read-only), Write
- MCPs: sentry (read-only)
- Output: /tmp/gorgias-troubleshoot/ only, JSON schema

**Cortex Agent (Restricted):**
- Bash (limited), Write
- MCPs: cortex
- Output: /tmp/cortex-agent/ only, JSON schema

**Knowledge Agent (Restricted):**
- Bash (limited), Write
- MCPs: Notion, Linear
- Output: /tmp/knowledge-agent/ only, JSON schema

## Constraints

- Main agent uses RTK (rtk grep, rtk find, rtk read) for exploration
- Browser agent returns JSON only; no prose
- Observability agent: Sentry/pup/gcloud read-only; no mutations
- All agents read security-scan.md before git commit/push/rebase
- Subagents never call each other's exclusive tools

## Build & Deploy

**Script:** `build-agents.sh` parses agent frontmatter → generates JSON config

```bash
./build-agents.sh [output-file]
```

See `DEPLOY.md` for deployment options (global or per-repo settings.json).

See `routing.md` for dispatch examples.
