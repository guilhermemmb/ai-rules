# Agent Routing Rules

Decision guide for main agent to delegate work to specialized subagents, or execute directly.

## Quick Reference

| Agent | Trigger | Access | Example |
|-------|---------|--------|---------|
| **main** | Code, git, tests, design, planning | Read, Edit, Write, Bash, codebase-memory-mcp, context7 | "Find where the auth middleware uses session tokens" |
| **browser-agent** | Screenshots, page interaction, UI inspection | chrome-devtools, superpowers-chrome | "Take a screenshot of the login page and extract the form fields" |
| **observability-and-troubleshoot** | Production errors, logs, metrics, traces | Sentry, Datadog, gcloud | "Find errors in helpdesk service last hour, root cause" |
| **cortex-agent** | Gorgias business metrics, schemas, definitions | cortex MCP | "What's the definition of MRR? Which tables store it?" |
| **knowledge-agent** | Notion docs, Linear issues, specs | notion, linear MCPs | "Find design docs for auth refactor. Get related Linear issues." |
| **planner** | Implementation strategy, architecture, design | All tools + reasoning | "Plan a refactor of the auth module" |

## Subagent Descriptions

### browser-agent

**Purpose:** Interact with web pages, take screenshots, extract UI data, test web behavior.

**Dispatch when:**
- Need browser interaction (click, type, navigate, fill forms, submit)
- Taking screenshots or inspecting page state
- Analyzing web UI, page content, DOM structure
- Running Lighthouse audits, performance traces
- Extracting data from web pages
- Testing web app behavior end-to-end

**What it can do:**
- Navigate to URLs
- Take screenshots (full page, viewport)
- Click elements, fill forms, submit
- Inspect DOM structure, page state
- Extract text, links, data from pages
- Run performance audits
- Test responsive design

**Main agent sends:**
- URL to navigate to
- Actions to perform (click, type, navigate)
- Data to extract or analyze
- Performance metrics to gather

**Receives back:**
- Screenshot paths
- Extracted data (JSON)
- Page state analysis
- Performance results
- Structured findings

---

### observability-and-troubleshoot

**Purpose:** Investigate production issues using error tracking, logs, metrics, and traces.

**Dispatch when:**
- Investigating production errors/incidents
- Need Sentry issue/event data or stack traces
- Querying logs (Datadog, GCP Logs)
- Analyzing metrics, traces, APM data
- Diagnosing latency/performance issues
- Root-cause analysis of deployment issues
- Understanding error patterns

**What it can do:**
- Query Sentry for issues, events, stack traces
- Search application logs (Datadog, GCP Logs)
- Analyze metrics, traces, APM data
- Find error patterns and signatures
- Correlate errors with deployments
- Diagnose latency and performance regressions
- Build root-cause hypotheses

**Main agent sends:**
- Service name
- Time window (e.g., "last 1h", "last 24h")
- Problem description (symptoms, errors)
- Filters (error type, endpoint, user, etc.)

**Receives back:**
- Error findings (count, frequency, affected users)
- Stack traces and error messages
- Log entries and context
- Metrics (latency, throughput, error rate)
- Root-cause hypothesis
- Suggested fixes

---

### cortex-agent

**Purpose:** Answer Gorgias business questions, provide metric definitions, schemas, and domain knowledge.

**Dispatch when:**
- Answer Gorgias business questions (metrics, revenue, churn, usage)
- Need metric definitions or table schemas
- Researching business rules, domain concepts
- Understanding customer data structure
- Analyzing financial/sales metrics
- Data model questions

**What it can do:**
- Define metrics (MRR, ARR, churn, NPS, etc.)
- Map metrics to database tables and columns
- Explain business rules and calculations
- Describe data model and relationships
- Query business data from BigQuery
- Analyze trends and patterns
- Answer strategic questions

**Main agent sends:**
- Business question (metric definition, schema, rule, trend)
- Context (time period, customer segment, etc.)

**Receives back:**
- Metric definitions and formulas
- Table schemas and column mappings
- Business rules and constraints
- Data examples and calculations
- Trend analysis
- Strategic insights

---

### knowledge-agent

**Purpose:** Find and summarize external documentation, design specs, feature requirements, and project tracking.

**Dispatch when:**
- Find design docs, specs, requirements (Notion)
- Search Linear issues, epics, feature requests
- Gather project documentation and context
- Get implementation details from external sources
- Understand past decisions and trade-offs
- Research customer needs (Notion)

**What it can do:**
- Search Notion databases and docs
- Find Linear issues, epics, feature requests
- Summarize design documents
- Extract technical specifications
- Gather context from customer feedback
- Track feature status and blockers
- Understand decision history

**Main agent sends:**
- Knowledge needed (docs, issues, specs)
- Search scope (Notion, Linear, or both)
- Keywords or filter criteria
- Context (project, feature, area)

**Receives back:**
- Documents with summaries
- Linear issues with details
- Design specifications
- Implementation context
- Decision history
- Customer feedback summaries

---

### planner

**Purpose:** Design implementation strategies, explore architectural trade-offs, plan multi-step refactors, design new features.

**Dispatch when:**
- Need to design implementation strategy
- Exploring architectural trade-offs
- Planning multi-step refactors
- Designing new features from requirements
- Making cross-system design decisions
- Uncertain about approach

**What it can do:**
- Design implementation approaches
- Evaluate trade-offs (performance, complexity, maintenance)
- Plan multi-file refactors
- Design feature architecture
- Identify critical files and dependencies
- Plan migration strategies
- Consider edge cases and risks

**Main agent sends:**
- Context, requirements, constraints
- Files/systems involved
- Trade-offs to evaluate
- Acceptance criteria

**Receives back:**
- Step-by-step implementation plan
- File-by-file approach
- Migration strategy
- Risk assessment
- Testing plan
- Rollback strategy (if needed)

---

## Direct Execution (Main Agent)

Main agent executes directly for:

- **Code exploration** — RTK grep, rtk find, codebase-memory-mcp search_graph, trace_path
- **Code modification** — Edit, Write files (non-browser, non-observability, non-domain)
- **Testing & linting** — pnpm test, pnpm lint (run & fix)
- **Builds & deploys** — ./deploy.sh, build scripts
- **Git operations** — `git commit`, `git push`, `git rebase` (with user confirmation)
- **GitHub operations** — `gh pr create/edit/merge`, `gh issue create/list`, `gh repo search` (via gh CLI)
- **Superpowers planning** — TaskCreate/TaskUpdate for plan tracking
- **Analysis & design** — Initial planning, architectural thinking (unless delegating to planner)

---

## When NOT to Dispatch

### Don't dispatch for simple exploration
```
❌ "Find where auth middleware uses session tokens" → Use codebase-memory-mcp search_graph directly
❌ "What's in the auth module?" → Use grep or codebase-memory-mcp
```

### Don't dispatch for simple code changes
```
❌ "Add console.log to debug" → Just edit the file
❌ "Fix typo in README" → Just edit directly
```

### Don't dispatch if main has the tool
```
❌ "Create a PR" → Use gh CLI directly, don't spawn github-agent
❌ "Search for an issue" → Use gh CLI directly
```

---

## Example Workflows

### GitHub Operations (Main Agent)
```
Task: Create a PR with specific title and description

main (via gh CLI):
  gh pr create --title "feat(auth): add jwt token refresh" \
    --body "Description..." --draft

Receives: PR URL and number
```

### Browser Interaction (Dispatch)
```
Task: Take screenshot of the login page

main → browser-agent:
  "Navigate to https://example.com/login and take a screenshot"

browser-agent ← Interacts with browser, captures screenshot

main ← screenshot_path
```

### Production Investigation (Dispatch)
```
Task: Find and diagnose errors in helpdesk service

main → observability-and-troubleshoot:
  "Service: helpdesk, time: last 1h, find errors and root cause"

observability-and-troubleshoot ← Queries Sentry, logs, metrics

main ← {errors: [...], root_cause: "...", suggested_fix: "..."}
```

### Business Knowledge (Dispatch)
```
Task: Understand MRR metric

main → cortex-agent:
  "What's the metric definition for MRR? Which tables contain MRR data?"

cortex-agent ← Queries cortex, BigQuery

main ← {definition: "...", formula: "...", tables: [...]}
```

### External Documentation (Dispatch)
```
Task: Find design docs for auth module refactor

main → knowledge-agent:
  "Search Notion for auth refactor design docs. Get related Linear issues."

knowledge-agent ← Searches Notion, Linear

main ← {docs: [...], issues: [...], key_points: [...]}
```

### Implementation Planning (Dispatch)
```
Task: Plan refactor of auth middleware

main → planner:
  "Design refactor of auth/middleware.ts: move session token logic to separate module.
   Files involved: middleware.ts, auth.ts, session.ts. Constraints: maintain backward compat."

planner ← Analyzes codebase, designs approach

main ← {steps: [...], files: [...], migration_plan: "...", risks: [...]}
```

### Code Exploration (Direct)
```
Task: Find all calls to auth middleware

main: (direct via codebase-memory-mcp)
  search_graph(function_name="authenticateRequest")
  trace_path(function_name="authenticateRequest", mode="inbound")

No dispatch needed — this is code exploration with tools main has access to.
```
