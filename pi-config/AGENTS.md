# User Instructions

These instructions override defaults in any loaded skill. As of Superpowers v5.0+,
user instructions take precedence over skill defaults.

## Planning Artifact Location

The canonical planning root for all projects is:

```
~/developer/planning-docs/{{repository-name}}/.planning/
```

Where `{{repository-name}}` is the directory name of the git repository root
(e.g. `ai-rules`, `my-project`). Resolve it from the working directory or git
remote.

When superpowers skills instruct saving artifacts to `docs/superpowers/`,
redirect them to the canonical planning root:

| Skill default | Canonical path |
|---|---|
| `docs/superpowers/specs/` | `~/developer/planning-docs/<repo>/.planning/specs/` |
| `docs/superpowers/plans/` | `~/developer/planning-docs/<repo>/.planning/plans/` |
| `sdd-workspace/` | `~/developer/planning-docs/<repo>/.planning/reports/` |
| Execution ledgers | `~/developer/planning-docs/<repo>/.planning/ledger-<plan>.md` |

Follow the storage contract in `.rulesync/rules/planning-state.md`:
- `specs/` — brainstorming design documents
- `plans/` — writing-plans output
- `reports/` — per-task implementation reports (executing-plans)
- `ledger-<plan>.md` — L/XL execution ledger at the planning root

Do not commit plan, spec, report, or ledger files to the project repository.

## Subagent Role Mapping (pi-subagents)

Superpowers skill templates dispatch with a generic `Subagent (general-purpose):`
header, but pi-subagents has no `general-purpose` agent. Map each superpowers
dispatch seat to the correct pi-subagents builtin role:

| Superpowers seat | pi-subagents role |
|---|---|
| Implementer (`implementer-prompt.md`) | `worker` — implementation work; edits, validates, escalates |
| Task reviewer (`task-reviewer-prompt.md`) | `reviewer` — code review and small fixes |
| Scoped re-review (`re-review-prompt.md`) | `reviewer` |
| Final code reviewer (`code-reviewer.md`) | `reviewer` (or `oracle` for the most-capable whole-branch review) |
| Spec/plan document reviewer | `oracle` / `advisor` — read-only critique |
| Generic one-off / small task | `delegate` — lightweight, parent-like child |

**Never use `delegate` for the implementer seat.** `delegate` is a generic
parent-like child without the `worker` role's edit/validate/escalate contract
and strict tool allowlist. Implementation always goes to `worker`.

Model routing for each role is declared in `settings.json` →
`subagents.agentOverrides` and in the `superpowers` profile under
`profiles/pi-subagents/`.
