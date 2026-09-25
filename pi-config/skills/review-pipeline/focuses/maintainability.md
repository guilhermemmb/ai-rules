# Maintainability Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Misleading names and inconsistent public contracts that hinder safe changes.
- Excessive coupling, circular dependencies and misplaced responsibilities.
- New behavior without meaningful tests; missing boundary/error scenarios.
- Tests without assertions, brittle mocks and tests tied to implementation detail.
- Non-obvious algorithms or public APIs lacking necessary documentation.
- Stale or misleading comments, unexplained constants and unsupported TODOs.
- Departure from established repository conventions without a concrete benefit.

Name the uncovered behavior and regression risk for a missing-test finding. Missing
tests, naming, absent JSDoc and circular imports do not automatically establish
critical impact. Check existing tests and conventions before proposing additions.
Avoid subjective style preferences. Correctness, performance, accessibility,
design and security defects belong to their own focuses.

Categories: `naming`, `coupling`, `tests`, `documentation`, `consistency`,
`organization`.
