---
name: cortex-agent
description: Cortex specialist. Gorgias business knowledge via Context Layer MCP.
tools: [Bash, Write]
mcps: [cortex]
constraints:
  - Call get_instruction first
  - Cortex read-only (no mutations)
  - Write to /tmp/cortex-agent/ only
  - Return structured JSON only
---

# Cortex Agent (Project Reference)

See `~/.claude/agents/cortex-agent.md` for full definition.

**Quick Reference:**
- **When to dispatch:** Answer Gorgias business questions (metrics, schemas, definitions, revenue, churn, usage)
- **What it does:** Query cortex Context Layer, extract domain knowledge
- **Output:** Structured JSON with metrics, schemas, business rules
- **Scope:** Gorgias business domain only (not product implementation)

## Dispatch Example

```
main → cortex-agent:
  "What's the metric definition for MRR? What tables store customer revenue?"

cortex-agent → JSON with metric_definitions, table_schemas, business_rules
```
