# Security Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- SQL/NoSQL, shell, HTML, URL/path and code injection; attacker-controlled regex.
- Missing authentication/authorization, weak tokens and sensitive endpoint abuse.
- CSRF in the actual authentication context and missing rate limits where material.
- Secrets in source/logs/errors, unsafe data exposure and credential transport.
- Input validation, file uploads, prototype pollution and unsafe deserialization.
- Changed dependency manifests/lockfiles, known relevant vulnerabilities, unsafe
  CORS/CSP settings, disabled certificate checks or weakened sandboxing.

Trace attacker-controlled input to a reachable sink and explain prerequisites and
impact. JSON.parse alone is not unsafe code execution; lack of a schema alone is
not a demonstrated vulnerability. Do not assert dependency vulnerabilities without
version/advisory evidence. Lack of permitted external lookup is a limitation, not
proof that a dependency is safe. Follow the agent's secret-handling policy in both
evidence and findings; never reproduce a credential to explain a finding.

Ignore general style, performance, whole-system threat modeling and speculative
compliance concerns outside the change.

Categories: `injection`, `auth`, `secrets`, `data-exposure`, `input-validation`,
`config`, `dependency`.
