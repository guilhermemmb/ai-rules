# Maintainability Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Misleading names and inconsistent public contracts that hinder safe changes.
- Excessive coupling, circular dependencies and misplaced responsibilities.
- Named changed behavior without a meaningful test for a concrete error path,
  boundary, negative case, asynchronous/concurrent outcome, or regression contract.
- Tests whose assertions do not exercise the contract that matters, brittle mocks,
  and tests tied to implementation detail that miss real regressions.
- Changed comments, docstrings, examples and affected nearby documentation for
  contradictions, obsolete symbols, unsupported claims, stale TODOs, narration-only
  text, or missing rationale for a genuinely non-obvious invariant or side effect.
- Departure from established repository conventions without a concrete benefit.

Name the uncovered behavior and regression risk for a missing-test finding. Do not
 demand numeric coverage, universal tests, comments for self-explanatory code, or
 unenforced documentation style. Missing tests, naming, absent JSDoc and circular
 imports do not automatically establish critical impact. Check existing tests and
 conventions before proposing additions. Avoid subjective style preferences.
 Correctness, performance, accessibility, design and security defects belong to their
 own focuses.

Categories: `naming`, `coupling`, `tests`, `documentation`, `consistency`,
`organization`.
