# General Review Focus

Apply the shared [report contract](../contracts.md) and [schema](../report.schema.json)
to the complete frozen evidence as one read-only AI reviewer. Do not dispatch
additional reviewers or modify files. Use only categories from the applicable
focuses supplied in the parent invocation; do not invent a general-only category.

Assess reachable correctness, security, simplicity, performance, accessibility,
maintainability, design consistency and Git-safety risks where relevant to the
actual changed files. Check the surrounding code and callers before raising an
issue. Anchor findings to frozen file/hunk IDs with specific impact and a
minimal, behavior-preserving fix. Omit irrelevant lenses rather than filling a
quota; record inaccessible content as omitted coverage, never as a pass.
