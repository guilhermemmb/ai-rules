## 1. data.yaml fixes

- [ ] 1.1 Remove duplicate `# Navigator → MCPs` comment at line 560 (stale copy above designer block)
- [ ] 1.2 Add missing link edges: detective → skill-dd-pup, skill-dd-apm, skill-dd-logs, skill-dd-monitors, skill-dd-debugger, skill-incident-response
- [ ] 1.3 Update Sage model name from `GPT-4o-mini` to match actual Bifrost model in oh-my-opencode-slim.json
- [ ] 1.4 Add six openspec skill nodes (openspec-propose, openspec-apply-change, openspec-archive-change, openspec-explore, openspec-update-change, openspec-sync-specs) under `# Skills` section with `parent: orchestrator`

## 2. index.html fixes

- [ ] 2.1 Add tools section: render `type: tool` nodes from data.yaml in a new `🛠️ Tools` section with similar layout to infra cards
- [ ] 2.2 Group skills by owner agent: change flat chip list to grouped sections labeled by parent agent name
- [ ] 2.3 Increase expanded card `max-height` from 600px to 1200px

## 3. summary.html rewrite

- [ ] 3.1 Rewrite summary.html to show current architecture: orchestrator as main card (dispatches to oracle, explorer, librarian, designer, fixer, observer, navigator, detective, sage), using same dark theme and chip visual style
- [ ] 3.2 Update each subagent card with correct name, model, trigger, and MCPs from data.yaml
- [ ] 3.3 Remove hardcoded `width: 1200px` from body; make it responsive (max-width instead)

## 4. README.md update

- [ ] 4.1 Rewrite the "Architecture" reference section (lines 167–229) replacing old agent names with current ones, matching data.yaml structure
- [ ] 4.2 Update MCP list under each agent to match current data.yaml mcp_access fields
- [ ] 4.3 Update skills list to include current skills from data.yaml
