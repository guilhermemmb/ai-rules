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

## Dispatch Graph

The following static Mermaid diagram is the high-level agent-to-agent dispatch map. The rendered version appears above the cards in `index.html`; it intentionally excludes MCPs, skills, tools, infrastructure, runtime data, and card interactions.

```mermaid
flowchart TD
    ORCH[Orchestrator] --> ORACLE[Oracle]
    ORCH --> EXPLORER[Explorer]
    ORCH --> LIBRARIAN[Librarian]
    ORCH --> DESIGNER[Designer]
    ORCH --> FIXER[Fixer]
    ORCH --> OBSERVER["Observer (auto-routes images)"]
    ORCH --> NAVIGATOR[Navigator]
    ORCH --> DETECTIVE[Detective]
    ORCH --> SAGE[Sage]
    ORCH --> REVIEWER[Reviewer]
    REVIEWER --> REVIEWERCODE["Reviewer Code"]
    REVIEWER --> REVIEWERCOMMENTS["Reviewer Comments (if docs)"]
    REVIEWER --> REVIEWERTEST["Reviewer Test (if tests)"]
    REVIEWER --> REVIEWERERRORS["Reviewer Errors (if errors)"]
    REVIEWER --> REVIEWERTYPES["Reviewer Types (if types)"]
    REVIEWER --> REVIEWERSIMPLIFIER["Reviewer Simplifier (sequential)"]
    REVIEWER --> REVIEWERACCESSIBILITY["Reviewer Accessibility (if UI files)"]
```

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

- Add/remove/rename agents in `.rulesync/subagents/`
- Modify MCPs or tool access in `.rulesync/rules/`
- Change subagent dispatch rules in `oh-my-opencode-slim.json`
- Update infrastructure/config in `.rulesync/mcp.jsonc`
- Modify skills in the global rules

### Claude Instruction

Add this reminder to `.rulesync/rules/custom-rules.md` or your memory:

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

**Built-in (Pantheon):**
- **orchestrator** — Master delegator; plans, implements directly, dispatches subagents
- **oracle** — Strategic advisor; architecture review, hard debugging, code review
- **explorer** — Codebase reconnaissance; broad searches, pattern discovery
- **librarian** — Knowledge retrieval; library docs (context7), web search, Linear, Gorgias internal docs/Notion (via Cortex), GitHub code search
- **designer** — UI/UX implementation; visual components, frontend polish, Figma Desktop
- **fixer** — Bounded implementation; scoped bug fixes, mechanical code changes
- **observer** — Visual analysis; images, screenshots, PDFs (auto-routed from orchestrator)

**Custom:**
- **navigator** — Browser automation; navigation, screenshots, DOM, form fills
- **detective** — Production diagnostics; Sentry, Datadog (pup CLI), GCP logs, Rootly, root cause analysis
- **sage** — Domain knowledge; Gorgias metrics, table schemas, business rules (cortex)

### MCPs (Model Context Protocol)

**orchestrator:**
- **codebase-memory-mcp** — Code search, graph-based exploration (shared by oracle, explorer, fixer, designer, detective, sage)
- **github** — GitHub CLI integration (PRs, issues, checks)

**librarian:**
- **context7** — Current library documentation
- **websearch** — Web search via Exa
- **gh_grep** — GitHub code search across repos
- **linear** — Issues, epics, cycles (read-only)
- **cortex** — Gorgias internal docs, specs, runbooks (read-only)

**designer:**
- **figma-desktop** — Design files (local Figma Desktop app, http://127.0.0.1:3845/mcp)

**navigator:**
- **mcp-server-browser** — Browser navigation, screenshots, interaction

**detective:**
- **sentry** — Error monitoring (read-only)
- **pup CLI** — Datadog CLI (--agent --ro): logs, metrics, APM, monitors
- **gcloud CLI** — GCP Cloud Logging (Bash, no enabled MCP)
- **rootly** — Incident management data

**sage:**
- **cortex** — Gorgias domain knowledge, metrics, BigQuery

### Tools
- **Bash** — Command execution (all agents)
- **Read/Edit/Write** — File operations (orchestrator, fixer, designer)
- **Git** — Version control (orchestrator)
- **gh CLI** — GitHub integration (orchestrator)

### Skills

**Orchestrator:**
- **codemap** — Repository cartography
- **deepwork** — Heavy session workflow
- **verification-planning** — Evidence before code
- **worktrees** — Isolated coding lanes
- **clonedeps** — Dependency X-ray
- **reflect** — Workflow self-improvement
- **oh-my-opencode-slim** — Plugin self-configuration
- **project-context** — Project summaries
- **openspec-propose / apply / archive / explore / update / sync** — SDD workflow

**Oracle:**
- **simplify** — Behavior-preserving refactors

**Detective:**
- **dd-pup** — Datadog CLI reference
- **dd-apm** — APM traces & services
- **dd-logs** — Log search & management
- **dd-monitors** — Monitor alerting
- **dd-debugger** — Live debugger probes
- **incident-response** — Incident tracking & on-call

### Infrastructure
- **OpenCode** — Entry point, OMO Slim plugin host
- **Oh My OpenCode Slim** — Agent orchestration (preset: bifrost)
- **Model Profiles** — Switch between `default` (performance) and `cost-efficient` (90% savings) via `deploy.sh --model-profile=<name>`
- **Bifrost** — Model gateway (https://bifrost.ops.gorgias.io)
- **RTK** — Token optimization plugin (~60-90% reduction)
- **zsh Environment** — Shell config (VOLTA_HOME, GORGIAS_ROOT, aliases)

## SDD Workflow — T-Shirt Sizing

The orchestrator always evaluates and visibly reports
`T-shirt size: XS | S | M | L | XL` with a short rationale first. The size
determines whether work is direct, uses a merged plan, or follows full SDD.

### T-shirt sizing policy

- **XS** — obvious isolated reversible edit. Execute immediately; no approval,
  artifact, or SDD.
- **S** — small local work following an established pattern.
- **M** — cohesive bounded work across related files without
  architecture/security/migration/data-integrity/external-integration
  uncertainty.
- **S/M** — use one concise merged SDD + implementation plan in
  `docs/.planning/plans/`, show it once, and obtain one approval before direct
  execution with proportionate validation. Do not create a separate spec, load
  `executing-plans`, create a ledger, run a per-task review, or prompt for a
  final review.
- **L** — multi-area/cross-system work or material uncertainty.
- **XL** — architecture, migration, security/data-integrity, production-impact,
  or major external-dependency work.
- **L/XL** — use full SDD. Show and approve a separate design/spec in
  `docs/.planning/specs/` before writing the implementation plan in
  `docs/.planning/plans/`; retain plan approval and the existing
  execution/review flow.

```mermaid
flowchart TD
    Start([User request]) --> Size["Report first:\nT-shirt size: XS | S | M | L | XL\n+ short rationale"]
    Size --> Triage{"T-shirt size?"}
    Triage -->|XS| XS1
    Triage -->|S/M| SM1
    Triage -->|L/XL| LX1

    subgraph XS["XS path"]
        direction TB
        XS1["Obvious isolated reversible edit"] --> Direct["Execute immediately\n(no approval, artifact, or SDD)"]
        Direct --> Done([Complete])
    end

    subgraph SM["S/M path"]
        direction TB
        SM1["S: small local established-pattern work\nM: cohesive bounded work across related files\n(no architecture/security/migration/data-integrity/\nexternal-integration uncertainty)"]
        SM2["Write one concise merged SDD + implementation plan\ndocs/.planning/plans/"]
        SM3["Show plan once"]
        SM4{"Approve plan once?"}
        SM5["Execute directly"]
        SM6["Proportionate validation\n(no separate spec, executing-plans, ledger,\nper-task review, or final-review prompt)"]
        SM7["Revise, clarify, or defer"]

        SM1 --> SM2
        SM2 --> SM3
        SM3 --> SM4
        SM4 -->|yes| SM5
        SM5 --> SM6
        SM6 --> Done
        SM4 -->|no| SM7
    end

    subgraph LX["L/XL path — full SDD"]
        direction TB
        LX1["L: multi-area/cross-system or material uncertainty\nXL: architecture, migration, security/data-integrity,\nproduction-impact, or major external-dependency work"]
        LX1 --> B1
    end

    subgraph Full1["🧠 L/XL — Phase 1: Brainstorming"]
        direction TB
        B1[Explore project context\n@explorer] --> B2[Research if needed\n@librarian / @oracle]
        B2 --> B3[Ask clarifying questions\none at a time]
        B3 --> B4[Propose 2-3 approaches\nwith trade-offs]
        B4 --> B5[Show separate design/spec]
        B5 --> B6{"Approve design/spec?"}
        B6 -->|revise| B5
        B6 -->|yes| B7[Save design/spec\ndocs/.planning/specs/]
        B7 --> B8[Spec self-review]
        B8 --> B9{"User approves spec?"}
        B9 -->|changes requested| B8
    end

    B9 -->|approved| P2

    subgraph P2["📋 L/XL — Phase 2: Writing Plans"]
        direction TB
        W1[Map file structure\n& task boundaries] --> W2[Decompose into\nbite-sized tasks 2-5min]
        W2 --> W3[Write implementation plan\ndocs/.planning/plans/\nwith Global Constraints]
        W3 --> W4{User approves plan?}
    end

    W4 -->|revise| W3
    W4 -->|approved| E1

    subgraph P3["⚡ L/XL — Phase 3: Executing Plans"]
        direction TB
        E1[Dispatch fresh agent\n@fixer code / @designer UI] --> E2{Report status?}
        E2 -->|NEEDS_CONTEXT| E1
        E2 -->|BLOCKED, context issue| E1
        E2 -->|BLOCKED, too hard| E5[Escalate to @oracle]
        E2 -->|DONE| E3[Dispatch @reviewer\nspec compliance + quality]
        E3 --> E4{Review passed?}
        E4 -->|no, up to 3 rounds| E1
        E4 -->|yes| E6{More tasks\nin plan?}
        E7{"Run optional final review?"}
        E6 -->|yes| E1
        E6 -->|no, all tasks done/parked| E7
        E5 --> E6
        E7 -->|yes| R1
        E7 -->|no| Done
    end

    subgraph P4["🔍 L/XL — Phase 4: Reviewing Plans"]
        direction TB
        R1[Gather plan + ledger\n+ full branch diff] --> R2[Dispatch @reviewer\nfull comprehensive review]
        R2 --> R3{Critical issues\n= 0?}
    end

    R3 -->|yes| Success([Plan executed with success\nready for merge/PR])
    R3 -->|no| Report[Report Critical issues\nto user — do NOT signal success]
    Report -.fix & re-review.-> R1
```

**Key rules baked into the flow:**

- Always report `T-shirt size: XS | S | M | L | XL` and a short rationale
  before taking action.
- XS work is immediate and has no approval, artifact, or SDD.
- S/M work gets one concise merged plan in `docs/.planning/plans/`, shown once
  and approved once before direct execution with proportionate validation. It
  skips a separate spec, `executing-plans`, a ledger, per-task review, and the
  final-review prompt.
- L/XL work is full SDD: show and approve the separate design/spec in
  `docs/.planning/specs/` before writing the implementation plan in
  `docs/.planning/plans/`, then retain plan approval and the existing
  execution/review flow.
- The fix loop in Phase 3 is capped at **3 rounds** before escalating to
  `@oracle`.
- Phase 4 is an **optional** final merge gate for L/XL work: any
  Critical issue blocks the "success" signal, regardless of how many tasks
  completed.

## Constraints

**Orchestrator hard-enforced dispatch rules (no direct access):**
- mcp-server-browser → dispatch to navigator
- sentry, rootly → dispatch to detective (gcp-logging disabled)
- cortex → dispatch to sage
- linear, cortex → dispatch to librarian (internal docs/Notion)

This enforces proper tool isolation and prevents unauthorized access.
