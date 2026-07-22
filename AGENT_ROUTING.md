# Agent Routing

Decision guide for choosing the right agent or tool for a task.

---

## Agents

### `planner`

**Use when:** The task requires planning before any code is written — feature spec, refactor strategy, bug investigation, architecture decisions.

**What it does:** Reads files, runs analysis commands, produces a detailed plan. It does NOT write code.

**Trigger:** User explicitly invokes it, or the task is complex enough to warrant planning before implementation.

**Files:** `.agents/agents/planner.md` / `planner.toml`

---

## Skills

Skills are invoked with `/skill-name` and provide focused task instructions.

| `/skill` | Use when |
|----------|---------|
| `/agent-browser-gorgias` | You need a browser session that persists Gorgias logins across days |
| `/gh-stack` | Creating, pushing, rebasing, or navigating a stack of dependent PRs |
| `/ha-api` | Working with Home Assistant automations, devices, areas, or entities via the JS API |
| `/project-context` | You need a structured summary of the current project before starting |
| `/react-doctor` | After React changes — scan for security, perf, correctness issues and get a 0–100 score |
| `/review-pr` | Review a PR for code quality, test coverage, documentation, and bugs |

---

## Built-in Commands

| Command | Use when |
|---------|---------|
| `git` operations | Always ask user first — never run git commands autonomously |
| `gh pr *` | Read-only only (`list`, `view`, `diff`, `checks`) — writing is blocked |
| `pnpm` | Default package manager — check project first |

---

## MCP Tools

| MCP | Use when |
|-----|---------|
| `HomeAssistant` | Controlling or querying Home Assistant via chat (requires HA to be reachable) |
| `serena` | Semantic code search or navigation within the current project |
| `context7` | Looking up current library/framework documentation |

---

## Decision Tree

```
Task needs planning before code?
  └─ yes → /planner

Task involves browser + Gorgias auth?
  └─ yes → /agent-browser-gorgias

Task involves stacked PRs?
  └─ yes → /gh-stack

Task involves React code?
  └─ finished implementing? → /react-doctor

Task involves Home Assistant?
  └─ need API reference? → /ha-api
  └─ need to control devices? → HomeAssistant MCP

Task involves reviewing a PR?
  └─ yes → /review-pr

Starting work on unfamiliar codebase?
  └─ yes → /project-context

Looking up library docs?
  └─ yes → context7 MCP
```
