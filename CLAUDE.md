# Global Instructions

## Branch Naming

- Always use `guilhermebomfim/` as the prefix (e.g. `guilhermebomfim/feature-name`), never `guilhermemmb/`

## GitHub Operations — gh CLI

Main agent uses `gh` CLI directly for GitHub operations. No MCP needed.

**Allowed gh commands:**

- `gh pr create/edit/merge/view/diff/checks`
- `gh issue create/edit/view/list`
- `gh repo search/list`
- `gh run list/view`
- `gh api` (GET only)

## Git Push Safety

- **Never use `git push --force`** — use `git push --force-with-lease` only when explicitly instructed after a rebase/amend
- Never force-push to `main`/`master` under any circumstances

## Forbidden Commands

- **NEVER run `gh run rerun`** or any command that triggers GitHub workflow runs
- The `collect` commands in gh-actions-metrics are read-only only

## Agent Configuration

Granular tool/MCP access per agent. Each agent handles specific domains:

| Agent | Purpose | MCPs | When to Dispatch |
|-------|---------|------|------------------|
| **main** | Orchestrator | codebase-memory-mcp, context7-mcp, github | Code exploration, implementation, gh CLI, dispatch |
| **browser-agent** | Browser interaction | mcp-server-browser, chrome-devtools-mcp | Navigation, screenshots, page analysis, web automation |
| **observability-and-troubleshoot** | Production diagnostics | sentry-mcp, datadog-mcp, gcloud, gcloud-observability, codebase-memory-mcp | Sentry/logs/metrics queries, root cause analysis, correlate telemetry to code |
| **cortex-agent** | Gorgias domain knowledge | cortex, codebase-memory-mcp | Metric definitions, schemas, business rules, map metrics to code |
| **knowledge-agent** | External docs & issues | notion, linear | Notion docs, Linear issues/epics, specs |

**Dispatch Rules:** See `agents/routing.md` for dispatch examples & detailed rules.

**Main Agent Constraints:**

- No mcp-server-browser, chrome-devtools-mcp (→ browser-agent)
- No sentry-mcp, datadog-mcp, gcloud, gcloud-observability (→ observability-and-troubleshoot)
- No cortex (→ cortex-agent)
- No notion, linear (→ knowledge-agent)

**Build & Deploy:** `./build-agents.sh` parses agent definitions, generates config. See `DEPLOY.md` for setup.

**RTK Usage:** Always prefer RTK commands (rtk grep, rtk find, rtk read) for exploration when available.

## Architecture Visualization

Keep `agents-overview/data.yaml` in sync with any agent/MCP/tool changes:

- **Agent added/removed/renamed?** → update `data.yaml` nodes + trigger/constraints/responsibilities
- **MCP access changed?** → update parent agent + constraints
- **Dispatch rules modified?** → update agent's trigger conditions + tools
- **Tool permissions updated?** → update tool's used_by field
- **Infrastructure config changed?** → update infra node details

**View:** Open `agents-overview/index.html` to see interactive architecture. No code needed—YAML drives everything.

**When:** After any changes to `agents/`, `MCP_SERVERS.md`, dispatch rules, or tool access.

## PR Workflow

When asked to "create PR", "open PR", "update PR", "draft PR", or similar:

1. **Title**: conventional commit format — `type(scope): description`, lowercase, no trailing period, ≤100 chars. Drop scope if unclear.

2. **Description**: use `.github/PULL_REQUEST_TEMPLATE.md` if present. Include before/after metrics table when applicable (lint counts, bundle size, test scores).

3. **Write to file** (never paste full description into chat):
   - `.context/pr/<branch-name>.md` if `.context/` exists
   - Otherwise `/tmp/pr-<branch-name>.md`
   - Format: first line `# <title>`, blank line, then body

4. **Show only** in chat: file path, one-line summary, and the exact `gh` command to run.

5. **Default to `--draft`** unless user says "ready for review".

6. **Reuse same file** when updating — overwrite it.

**Commands to give the user:**

```sh
# Create draft PR
gh pr create --base <base> --draft \
  --title "$(head -1 <file> | sed 's/^# //')" \
  --body-file <(tail -n +3 <file>)

# Update existing PR
gh pr edit <number> \
  --title "$(head -1 <file> | sed 's/^# //')" \
  --body-file <(tail -n +3 <file>)
```
