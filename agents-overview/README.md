# AI Rules Architecture Overview

Interactive visualization of agents, MCPs, tools, skills, and infrastructure in the ai-rules system.

**🔗 [Open Visualization](./index.html)** — Click to view the full architecture diagram in your browser.

## Files

- `index.html` — Interactive visualization engine (loads data dynamically from YAML)
- `data.yaml` — All node and configuration data (edit this to change the graph)
- `README.md` — This file

## Quick Start

The page uses `fetch()` to load `data.yaml`, so it must be served over HTTP (not opened as a `file://` URL).

```sh
# Serve and open in browser (runs on http://localhost:8888)
./agents-overview/serve.sh
```

Click any card to expand and see detailed information — constraints, responsibilities, tools, and configuration.

## Using the Visualization

**Navigation:**

- **Click cards** to expand/collapse and see full details
- **Scroll** to browse all sections
- **Responsive** — works on desktop and mobile

**Color coding:**

- Blue boxes — Agents
- Purple badges — MCPs
- Green badges — Tools
- Amber badges — Skills
- Pink boxes — Infrastructure

## Updating the Architecture

Edit `data.yaml` to keep the visualization in sync with your system. No code changes needed.

### Node Fields

```yaml
nodes:
  - id: unique-id                 # Required: unique identifier
    label: Display Name            # Required: shown in UI
    type: agent|mcp|tool|skill|infra  # Required: node category
    role: Brief role description   # Required: 1-line summary
    color: '#hexcolor'             # Required: badge/box color
    parent: parent-id              # Optional: nesting (agent contains MCPs)
    trigger: When to dispatch      # Agents: conditions for dispatch
    tools: Tool names              # Agents: available MCPs/tools
    constraints: Cannot access X   # Agents: access restrictions
    responsibilities: What it does # Agents: bullet-point list
    description: Brief description # Tools/Skills: what it does
    used_by: Which agents          # Tools: who uses it
    when: When to invoke           # Skills: when to use
    location: File path            # Infrastructure: config location
    config: Configuration details  # Infrastructure: setup details
```

### Adding an Agent

```yaml
nodes:
  - id: my-agent
    label: my-agent
    type: agent
    role: Specific purpose
    color: '#60a5fa'
    parent: main
    trigger: Conditions to dispatch
    tools: List of available MCPs
    constraints: Access restrictions
    responsibilities: |
      • Responsibility 1
      • Responsibility 2
```

### Adding an MCP

```yaml
nodes:
  - id: my-mcp
    label: my-mcp-name
    type: mcp
    role: What it provides
    color: '#a78bfa'
    parent: agent-id  # Which agent owns it
```

### Adding a Tool

```yaml
nodes:
  - id: my-tool
    label: My Tool
    type: tool
    role: What it does
    color: '#34d399'
    parent: null
    description: Detailed description
    used_by: Which agents use it
```

### Adding Infrastructure

```yaml
nodes:
  - id: my-config
    label: Config Name
    type: infra
    role: What it configures
    color: '#f472b6'
    parent: null
    location: ~/.config/file.json
    config: |
      • Configuration option 1
      • Configuration option 2
```

## Maintenance & Sync

### When to Update `data.yaml`

Update the visualization whenever you change:

- Add/remove/rename agents in `agents/`
- Modify MCPs or tool access in `CLAUDE.md`
- Change subagent dispatch rules in `agents/routing.md`
- Update infrastructure/config in `MCP_SERVERS.md`
- Modify skills in the global rules

### Claude Instruction

Add this reminder to CLAUDE.md or your memory:

```markdown
## Architecture Visualization

Keep `agents-overview/data.yaml` in sync with agent/MCP/tool changes:

- Agent added? → update nodes, add trigger/constraints/responsibilities
- MCP access changed? → update parent/constraints
- Dispatch rules modified? → update agent's trigger conditions
- Tool permissions updated? → update tool's used_by field
- Infrastructure config changed? → update infra node details

Changes are immediately reflected in the visualization at `agents-overview/index.html`.
```

### Quick Reference

After any agent/MCP/tool changes:

1. Edit `agents-overview/data.yaml`
2. Refresh `index.html` in browser
3. Verify visualization matches actual system

No code needed—YAML drives everything.

## Architecture

### Agents
- **main** — Orchestrator, dispatches work to specialized agents
- **browser-agent** — Browser interaction (screenshots, automation)
- **observability-and-troubleshoot** — Production diagnostics (logs, metrics, errors)
- **cortex-agent** — Gorgias domain knowledge (metrics, schemas)
- **knowledge-agent** — External docs (Notion, Linear)

### MCPs (Model Context Protocol)

**main agent:**

- **codebase-memory-mcp** — Code search, graph-based exploration
- **context7-mcp** — Current library documentation
- **github** — GitHub CLI integration (PRs, issues, checks)

**browser-agent:**

- **mcp-server-browser** — Browser navigation, screenshots, interaction (tier 1)
- **chrome-devtools-mcp** — Performance profiling, Lighthouse, network inspection (tier 2)

**observability-and-troubleshoot:**

- **sentry-mcp** — Error monitoring (read-only)
- **datadog-mcp** — APM, logs, metrics (read-only)
- **gcloud** — GCP Cloud Logging
- **gcloud-observability-ai-agent** — GCP Observability for gorgias-conversations-prod (always paired with gcloud)
- **gcloud-observability-chat** — GCP Observability for gorgias-chat-production (always paired with gcloud)

**cortex-agent:**

- **cortex** — Gorgias domain knowledge, metrics, BigQuery

**knowledge-agent:**

- **notion** — Knowledge base docs
- **linear** — Issues and epics

**personal (main session only):**

- **HomeAssistant** — Home automation control

### Tools
- **Bash** — Command execution
- **Read/Edit/Write** — File operations
- **Git** — Version control
- **gh CLI** — GitHub integration

### Skills
- **superpowers** — Planning, debugging, brainstorming
- **code-review** — PR analysis and code review
- **caveman** — Terse communication mode

### Infrastructure
- **Claude Code** — IDE integration
- **settings.json** — MCP and tool configuration
- **zsh Environment** — Shell configuration
- **RTK** — Token optimization for CLI commands

## Constraints

**Main agent cannot directly access:**
- mcp-server-browser, chrome-devtools-mcp (→ dispatch to browser-agent)
- sentry-mcp, datadog-mcp, gcloud, gcloud-observability-ai-agent, gcloud-observability-chat (→ dispatch to observability-and-troubleshoot)
- cortex (→ dispatch to cortex-agent)
- notion, linear (→ dispatch to knowledge-agent)

This enforces proper tool isolation and prevents unauthorized access.
