# Global Instructions

## Branch Naming

- Always use `guilhermebomfim/` as the prefix (e.g. `guilhermebomfim/feature-name`), never `guilhermemmb/`

## GitHub Operations — Delegated to github-agent

Main agent does NOT call GitHub tools. All GitHub operations delegated to `github-agent` subagent.

**github-agent handles:**

- PR operations (create, list, view, diff, edit, merge, review, comment)
- Issue operations (create, list, view, search, edit, comment)
- Repository operations (search, list)
- Branch operations (create, list, delete)
- Workflow operations (list, view)

**Main agent responsibility:**

- Describe the GitHub task (PR creation, issue search, etc.)
- Provide context (title, description, filters)
- Wait for structured response
- Do NOT call GitHub tools directly

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
| **main** | Orchestrator (no elevated access) | codebase-memory-mcp, context7 | Code exploration, implementation, dispatch |
| **github-agent** | GitHub operations | github | PR/issue creation, search, review, merge |
| **browser-agent** | Browser interaction | chrome-devtools, superpowers-chrome | Screenshots, page analysis, web interaction |
| **observability-and-troubleshoot** | Production diagnostics | sentry, datadog, gcloud | Sentry/logs/metrics queries, root cause analysis |
| **cortex-agent** | Gorgias domain knowledge | cortex | Metric definitions, schemas, business rules |
| **knowledge-agent** | External docs & issues | notion, linear | Notion docs, Linear issues/epics, specs |

**Dispatch Rules:** See `agents/routing.md` for dispatch examples & detailed rules.

**Main Agent Constraints:**

- No github (→ github-agent)
- No chrome-devtools, superpowers-chrome (→ browser-agent)
- No sentry, datadog, gcloud (→ observability-and-troubleshoot)
- No cortex (→ cortex-agent)
- No notion, linear (→ knowledge-agent)

**Build & Deploy:** `./build-agents.sh` parses agent definitions, generates config. See `DEPLOY.md` for setup.

**RTK Usage:** Always prefer RTK commands (rtk grep, rtk find, rtk read) for exploration when available.

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
