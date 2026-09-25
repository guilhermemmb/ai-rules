# Accessibility Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Native semantic elements, meaningful heading/list/table structure.
- Accessible names, valid roles, ARIA references and state attributes.
- Keyboard operability, focus visibility/order, traps and dialog focus restoration.
- Labels, required fields, error associations and placeholder-only instructions.
- Informative versus decorative image alternatives and icon-only control names.
- Hidden content, dynamic announcements and state communicated only through color.
- CSS changes that hide focus indicators or make content inaccessible.

Missing tabindex is not a defect on an already keyboard-operable native element.
Decorative images/SVGs need not be announced. Cite the actual affected interaction
and user impact; distinguish verified conformance failures from best-practice
suggestions. Diff inspection alone is not a full WCAG audit or runtime keyboard,
contrast or screen-reader test. State what could not be verified with available
agent tools rather than claiming visual or assistive-technology validation.

Categories: `semantic-html`, `aria`, `keyboard`, `focus`, `forms`, `alt-text`,
`screen-reader`, `labels`.
