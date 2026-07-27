## ADDED Requirements

### Requirement: summary.html reflects current OMO Slim agents
`summary.html` SHALL display the 10 current agents: orchestrator (center), oracle, explorer, librarian, designer, fixer, observer (built-in Pantheon), and navigator, detective, sage (custom). Old names (main, browser-agent, cortex-agent, knowledge-agent, planner) SHALL NOT appear.

#### Scenario: Accurate agent names in summary
- **WHEN** a user opens summary.html in a browser
- **THEN** they see orchestrator as the main card and the 9 subagents in the grid with correct names, roles, and MCPs

#### Scenario: No stale agent names
- **WHEN** the file is searched for old names
- **THEN** strings "browser-agent", "cortex-agent", "knowledge-agent", "observability-and-troubleshoot", "planner" are not found anywhere in summary.html

### Requirement: README.md architecture section is current
The architecture reference section of `README.md` (agents, MCPs, skills, tools) SHALL list only current agent names and their MCPs, matching data.yaml.

#### Scenario: Consistent with data.yaml
- **WHEN** the README architecture section is compared to data.yaml agents
- **THEN** every agent listed in README matches an id in data.yaml nodes

### Requirement: data.yaml skill links for detective are complete
Every skill node with `parent: detective` SHALL have a corresponding link edge `source: detective → target: skill-*` in the `links:` section.

#### Scenario: Detective skill edges present
- **WHEN** data.yaml links section is inspected
- **THEN** detective → skill-dd-pup, skill-dd-apm, skill-dd-logs, skill-dd-monitors, skill-dd-debugger, skill-incident-response links are all present

### Requirement: data.yaml has no duplicate or stale comments
The `links:` section SHALL NOT contain two consecutive `# Navigator → MCPs` comments.

#### Scenario: No duplicate Navigator comment
- **WHEN** data.yaml is searched for "# Navigator"
- **THEN** exactly one such comment exists (at the correct location above navigator links)

### Requirement: openspec skills are represented in data.yaml
The six openspec workflow skills (openspec-propose, openspec-apply-change, openspec-archive-change, openspec-explore, openspec-update-change, openspec-sync-specs) SHALL exist as skill nodes in data.yaml with `parent: orchestrator`.

#### Scenario: openspec skill nodes present
- **WHEN** data.yaml nodes are filtered by type: skill
- **THEN** at least the six openspec skill ids are found

### Requirement: index.html renders tool nodes
`index.html` SHALL include a rendered section for `type: tool` nodes from data.yaml (currently silently dropped).

#### Scenario: Tools section visible
- **WHEN** index.html is loaded in browser and page is scrolled
- **THEN** a "Tools" section appears showing Bash, Read/Edit/Write, Git, and gh CLI

### Requirement: index.html groups skills by owner agent
The Skills section in `index.html` SHALL group skill chips by their parent agent rather than showing all skills as a flat unsorted list.

#### Scenario: Skills grouped by parent
- **WHEN** index.html Skills section is viewed
- **THEN** skills are visually grouped under their owner agent labels (e.g., "Orchestrator", "Detective", "Oracle")

### Requirement: Expanded agent cards do not clip content
`index.html` SHALL set `max-height` on expanded agent cards to at least 1200px so that agents with long responsibilities + constraints (e.g., detective) are fully visible.

#### Scenario: Detective card fully visible when expanded
- **WHEN** the Detective card is clicked to expand
- **THEN** all responsibilities and constraints are visible without scrolling within the card
