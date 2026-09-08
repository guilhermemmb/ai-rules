# Architecture

OpenCode uses the orchestrator as the review manager. Navigator and Oracle
retain their existing responsibilities. Review work is delegated to one
read-only `reviewer` agent configured with `bf-o/gpt-5.6-luna` (medium) and
`serena`, `context7`, and `gh_grep`.

The review registry is contract version 2. A batch review is created after every
fixer in a completed batch has a terminal report and changed-path
reconciliation. The batch is represented by one immutable packet and one
consolidated report; dependent batches wait until that report is reconciled.
The review pipeline selects focus IDs from the canonical catalog and dispatches
a fresh reviewer invocation for each selected focus, with a unique invocation
ID and the registry cap of at most ten concurrent reviewer tasks. Focuses are
`code`, `tests`, `errors`, `types`, `security`, `performance`, `data-integrity`,
`accessibility`, `comments`, and `simplify`. There is no phase dependency.

After all fixer batches are reconciled, one mandatory full-branch review report
is required before final handoff or commit authorization. Review findings are
report-only; the user chooses whether to fix, defer, or accept them. Health
failures remain health-first and are reported as degraded or inconclusive.
Commits still require the separate Git security scan.
