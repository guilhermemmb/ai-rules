## Why

The `agents-overview/` directory was never updated after migrating to Oh My OpenCode Slim. `summary.html` and `README.md` still reference the old agent names (`main`, `browser-agent`, `cortex-agent`, `knowledge-agent`, `planner`), making them misleading and inaccurate. `data.yaml` and `index.html` also have several gaps.

## What Changes

- **`summary.html`** — Completely rewrite to reflect current OMO Slim architecture (orchestrator, navigator, detective, sage, librarian, explorer, oracle, designer, fixer, observer)
- **`README.md`** — Rewrite the "Architecture" reference section (agents, MCPs, skills) at the bottom with current names
- **`data.yaml`** — Fix four issues:
  - Add missing `detective → skill-dd-*` links in the `links:` section
  - Remove duplicate `# Navigator → MCPs` comment (line 560, stale copy of designer block)
  - Update Sage model from `GPT-4o-mini` to current Bifrost naming
  - Add missing openspec-* skills nodes (propose, apply, archive, explore, update, sync)
- **`index.html`** — Fix three rendering issues:
  - Add tools section (type: tool nodes currently not rendered)
  - Group skills by owner agent instead of flat chips
  - Increase `max-height` on expanded cards from 600px to 1200px

## Capabilities

### New Capabilities

- `agents-overview-accuracy`: Agents overview stays accurate and complete — summary, README, YAML, and UI all reflect the same current architecture

### Modified Capabilities

- none

## Impact

- `agents-overview/summary.html` — full rewrite
- `agents-overview/data.yaml` — targeted edits (links, comments, model name, new skill nodes)
- `agents-overview/index.html` — targeted JS/CSS edits (tools section, skill grouping, max-height)
- `agents-overview/README.md` — rewrite architecture reference section
