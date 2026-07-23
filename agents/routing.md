# Agent Routing Rules

Dispatch rules for main agent to delegate work to subagents.

## When to Use Each Subagent

### browser-agent
**Dispatch when:**
- Goal involves browser interaction (click, type, navigate, fill forms)
- Need to take screenshots or inspect page state
- Analyzing web UI, page content, DOM structure
- Running Lighthouse audits, performance traces
- Extracting data from web pages
- Testing web app behavior end-to-end

**Main agent responsibility:**
- Describe the goal (URL, actions, what to extract)
- Wait for structured JSON response
- Do NOT call chrome-devtools tools directly

### observability-and-troubleshoot
**Dispatch when:**
- Investigating production errors/incidents
- Need Sentry issue/event data or stack traces
- Querying logs (Datadog, GCP Logs)
- Analyzing metrics, traces, APM data
- Diagnosing latency/performance issues
- Root-cause analysis of deployment issues

**Main agent responsibility:**
- Describe the problem (service, time window, symptoms)
- Specify time range and filters
- Wait for structured JSON findings
- Do NOT call Sentry/pup/gcloud tools directly

### cortex-agent
**Dispatch when:**
- Answer Gorgias business questions (metrics, revenue, churn, usage)
- Need metric definitions or table schemas
- Researching business rules, domain concepts
- Understanding customer data structure
- Analyzing financial/sales metrics

**Main agent responsibility:**
- Ask specific business domain questions
- Wait for structured knowledge response
- Do NOT call cortex MCP directly

### knowledge-agent
**Dispatch when:**
- Find design docs, specs, requirements (Notion)
- Search Linear issues, epics, feature requests
- Gather project documentation and context
- Get implementation details from external sources

**Main agent responsibility:**
- Describe what knowledge is needed (docs, issues, specs)
- Specify search scope (Notion, Linear, or both)
- Wait for structured findings
- Do NOT call notion/linear MCPs directly

### planner
**Dispatch when:**
- Need to design implementation strategy
- Exploring architectural trade-offs
- Planning multi-step refactors
- Designing new features from requirements
- Making cross-system design decisions

**Main agent responsibility:**
- Provide context, requirements, constraints
- Wait for detailed plan
- Review and approve before main agent executes

## Direct Execution (Main Agent)

Main agent executes directly for:
- Code reading & exploration (RTK grep, rtk find, codebase-memory-mcp)
- Writing/modifying code (non-browser, non-observability, non-domain-knowledge)
- Running tests, linting, builds
- Git operations (with user confirmation)
- Task management (TaskCreate/Update)
- Planning & design (unless delegating to planner)

Main agent does **NOT** have access to:
- Browser tools (delegated to browser-agent)
- Observability tools (delegated to observability-and-troubleshoot)
- Cortex MCP (delegated to cortex-agent)
- Notion/Linear (delegated to knowledge-agent)

## Example Workflows

### "Take a screenshot of the login page"
```
main → browser-agent:
  "Navigate to https://example.com/login and take a screenshot"
main ← JSON with screenshot_paths
```

### "Find errors in helpdesk service last hour"
```
main → observability-and-troubleshoot:
  "Service: helpdesk, time: last 1h, find errors and root cause"
main ← JSON with sentry_findings, logs, root_cause_hypothesis
```

### "What's the definition of MRR? What tables store it?"
```
main → cortex-agent:
  "What's the metric definition for MRR? Which tables contain MRR data?"
main ← JSON with metric_definitions, table_schemas, business_rules
```

### "Find design docs for the auth module refactor. Get related Linear issues."
```
main → knowledge-agent:
  "Search Notion for auth refactor docs. Get Linear issues about auth."
main ← JSON with documents[], issues[], key_points
```

### "Plan a refactor of the auth module"
```
main → planner:
  "Design refactor of auth/middleware.ts: move session token logic to separate module"
main ← detailed plan with files, approach, migration strategy
```

### "Find where auth middleware uses session tokens"
```
main: use codebase-memory-mcp search_graph or grep directly
(no subagent needed — this is code exploration)
```
