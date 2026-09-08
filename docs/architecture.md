# Architecture

OpenCode uses the orchestrator as the review manager. Navigator and Oracle
retain their existing responsibilities. Review work is delegated to one
read-only `reviewer` agent configured with `bf-o/gpt-5.6-luna` (medium) and
`serena`, `context7`, and `gh_grep`.

The review registry is contract version 2. A run selects focus IDs from the
catalog and dispatches a fresh reviewer invocation for each selected focus,
with a unique invocation ID and at most three concurrent tasks. Focuses are
`code`, `tests`, `errors`, `types`, `security`, `performance`, `data-integrity`,
`accessibility`, `comments`, and `simplify`. There is no phase dependency.
