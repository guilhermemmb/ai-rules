## Context

`agents-overview/` is a static visualization driven by `data.yaml`. Four files need updating: `data.yaml` (source of truth), `index.html` (renderer), `summary.html` (snapshot), and `README.md` (docs). The current state has the last three frozen at a pre-OMO-Slim agent layout, and the YAML has accumulated gaps: missing skill links, a stale comment, an outdated model name, and missing skill nodes.

## Goals / Non-Goals

**Goals:**
- All four files accurately describe the current OMO Slim agent architecture
- `index.html` renders all node types (including tools, skills grouped by owner)
- `summary.html` shows the correct 10-agent layout
- `data.yaml` is internally consistent (all nodes have corresponding link edges where needed)

**Non-Goals:**
- Redesigning the visualization layout or interaction model
- Adding new visualization features beyond the identified gaps
- Touching any file outside `agents-overview/`

## Decisions

**D1: Rewrite summary.html from scratch vs. patch**
Patching would require replacing nearly every string. A full rewrite is cleaner and produces a consistent result. Preserving the existing visual style (dark theme, 3-column grid, badge chips) is intentional.

**D2: Skills grouping in index.html**
Instead of flat chips, skills are shown grouped by owner agent using a `<details>` expand pattern or simple labeled sub-sections. No new dependencies — pure DOM manipulation within the existing render pipeline.

**D3: Sage model name**
`GPT-4o-mini` is the OpenAI public name. The Bifrost naming convention for this slot would be `GPT-4o mini` or left as-is if the model is provisioned under that name. Decision: update to match the actual Bifrost model ID used in `oh-my-opencode-slim.json`.

**D4: openspec-* skills scope**
Add the 6 openspec skills (propose, apply, archive, explore, update, sync-specs) as skill nodes with `parent: orchestrator`. They are meta-workflow skills invoked by the orchestrator.

## Risks / Trade-offs

- `summary.html` rewrite may diverge from visual intent if the reviewer's eye differs from original author intent → Mitigation: preserve exact color palette and layout grid.
- Adding openspec skill links could make the orchestrator node very busy in any future graph view → Mitigation: acceptable for now; omit links for openspec skills (they're invoked ad-hoc, not dispatched like agents).
