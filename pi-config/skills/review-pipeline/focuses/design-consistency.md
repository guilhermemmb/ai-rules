# Design Consistency Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Colors, spacing, type, shadows, radii, breakpoints and layering against tokens.
- Component reuse, composition and API/variant consistency.
- Layout, alignment and responsive behavior against established patterns.
- Hover/focus/active/disabled, loading and empty states when required by the flow.
- Icon sets/sizes and responsive imagery.

Cite the existing token, component or documented convention. Do not invent a design
system requirement or treat every hardcoded value as a defect. A duplicated
component alone is not critical; assess demonstrated user or maintenance impact.
Without visual/runtime evidence, report a supported regression risk rather than
claiming a verified visual failure. Ignore personal aesthetic preferences and
whether the design itself is desirable. Accessibility, correctness and performance
belong to their own focuses.

Categories: `tokens`, `spacing`, `typography`, `component-api`, `states`, `icons`,
`layout`, `responsive`.
