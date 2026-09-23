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
