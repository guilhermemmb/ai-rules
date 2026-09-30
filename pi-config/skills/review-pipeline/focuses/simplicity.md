# Simplicity Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Unnecessary layers, indirection or generic configuration without a present use.
- Dead imports, unused exports, unreachable paths and obsolete fallback code.
- Commented-out implementation and abandoned scaffolding.
- Complex branching, mixed abstraction levels and boolean-controlled behaviors.
- Duplication where an existing helper or mechanism has demonstrable reuse benefit;
  search for it before claiming duplication.
- Redundant or derivable state, deep nesting, fragile special cases and abstraction
  altitude mismatches only when a behavior-preserving simpler alternative is clear.

Check callers before calling an export unused. Existing project requirements may
justify abstractions, internationalization or multi-tenancy; do not infer YAGNI
from one diff. Explain the maintenance cost and propose a simpler alternative
without changing behavior. Line counts and number of implementations are clues,
not automatic defects. Do not suggest taste-only or subjective cleanup, or refactors
that change behavior. Pure naming/style, test coverage and speculative future
requirements are outside this lens.

Categories: `dead-code`, `over-abstraction`, `complexity`, `yagni`, `duplication`,
`indirection`.
