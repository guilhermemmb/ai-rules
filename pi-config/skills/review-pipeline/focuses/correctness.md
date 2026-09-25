# Correctness Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Null/undefined access, empty inputs, boundary values, off-by-one errors.
- Incorrect conditions, coercion, fallthrough and numeric assumptions.
- Async ordering, missing awaits, races and resource cleanup.
- Broken API/type contracts, unexpected mutation and compatibility regressions.
- Swallowed exceptions, missing propagation and loss of error context.
- Changed behavior against callers and relevant tests, not the diff in isolation.

Only report concrete defects introduced or made reachable by the change. Trace a
failure path and anchor it to a changed line or deletion. General style,
performance, design and test-coverage adequacy belong to their own focuses.

Categories: `null-safety`, `edge-case`, `error-handling`, `contract`, `logic`,
`race-condition`, `resource-leak`.

No focus-specific finding cap: report all supported findings or disclose omitted
output with `findings_omitted` and an error. Empty findings require complete
coverage before this focus can pass.
