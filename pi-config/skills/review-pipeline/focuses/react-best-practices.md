# Vercel React Best Practices Focus

Apply this lens as the predefined read-only reviewer. Follow the shared
[report contract](../contracts.md) and schema. Review only the frozen React/Next
package evidence and the changed file/hunk inventory supplied by the parent.

Read the globally installed pinned `vercel-react-best-practices` `SKILL.md` and
only the individual rule files relevant to the changed code; do not load every
rule or treat the compiled `AGENTS.md` as a prompt. For every finding, cite one
applicable Vercel `rule_id` from a real rule filename and use the matching family
as `category`: `async`, `bundle`, `server`, `client`, `rerender`, `rendering`,
`js`, or `advanced`.

Investigate only reachable, change-introduced performance risks in the actual
React/Next runtime and version context. A published rule impact, missing pattern,
benchmark absence, or library preference alone is not a defect and does not
choose the report severity. Anchor every finding to frozen hunk/file IDs, explain
impact, and propose the smallest appropriate fix. If package or rule evidence is
unavailable, report an error and omitted coverage; do not claim a pass or launch
other reviewers.
