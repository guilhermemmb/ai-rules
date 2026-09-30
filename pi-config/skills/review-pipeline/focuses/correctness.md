# Correctness Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Null/undefined access, empty inputs, boundary values, off-by-one errors.
- Incorrect conditions, coercion, fallthrough and numeric assumptions.
- Async ordering, missing awaits, races, unsafe shared state and resource cleanup.
- Catch-and-continue behavior, broad catches, swallowed asynchronous errors,
  fallbacks/defaults that erase failures, retries that lose the original cause, and
  state that proceeds as if an operation succeeded. Distinguish surfaced deliberate
  degradation from hidden failure and name the masked failure path.
- Broken API/type contracts, unexpected mutation and compatibility regressions.
- Swallowed exceptions, missing propagation and loss of error context.
- Changed behavior against callers and relevant tests, not the diff in isolation.
- Configuration changes against their actual consumers: defaults, environment
  precedence, build/workflow conditions, dependency scripts and compatibility.
  Parseable configuration can still change behavior incorrectly; trace the consumer.
- Changed migrations, persistence operations, query builders, indexes and
  planner-sensitive code for data loss, heavy locks, table rewrites, unsafe rolling
  deployment sequencing, missing supporting indexes, and repository-required
  query-plan evidence. Require a concrete deployment or execution consequence; do
  not require query plans for trivial or obviously indexed work unless repository
  policy requires them.

Only report concrete defects introduced or made reachable by the change. Trace a
failure path and anchor it to a changed line or deletion. General style,
performance, design and test-coverage adequacy belong to their own focuses.

Categories: `null-safety`, `edge-case`, `error-handling`, `contract`, `logic`,
`race-condition`, `resource-leak`.

No focus-specific finding cap: report all supported findings or disclose omitted
output with `findings_omitted` and an error. Empty findings require complete
coverage before this focus can pass.
