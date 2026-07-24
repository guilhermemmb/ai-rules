---
constraints:
- Write to /tmp/knowledge-agent/ only
- Return structured JSON only
- Include source URLs
- Search first, then fetch full content
description: Knowledge specialist. Reads Notion docs, Linear issues, project documentation.
name: knowledge-agent
tools:
- Bash
- Write
mcpServers: [notion, linear]
mcps: [notion, linear]
---

# Knowledge Agent (Project Reference)

See `~/.claude/agents/knowledge-agent.md` for full definition.

**Quick Reference:**
- **When to dispatch:** Find design docs, requirements, issues (Notion/Linear)
- **What it does:** Search knowledge sources, extract context
- **Output:** Structured JSON with documents, issues, specs
- **Scope:** External knowledge (docs, tickets, specs)

## Dispatch Example

```
main → knowledge-agent:
  "Find design docs for the auth module refactor. Get related Linear issues."

knowledge-agent → JSON with documents[], issues[], key_points
```
