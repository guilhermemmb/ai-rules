# Git Safety Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Real credentials, private keys, tokens, credential-bearing URLs and sensitive
  dumps/configuration in changed content or tracked file metadata.
- Generated output, dependencies, build artifacts and unexpectedly large binaries.
- Backup/log/core-dump files, OS metadata and unintended IDE settings.
- Missing ignore patterns for newly generated or sensitive artifacts.
- Conflict markers, obscuring whitespace-only churn and abandoned commented code.

Follow agent policy when handling secrets; describe the type and location without
reproducing values. Recommend rotation when exposure is established. Public keys,
certificates, example .env values and intentional shared IDE settings are not
necessarily secrets or accidental files. Size thresholds are investigation hints,
not automatic severity. For binary/file-only findings use `side: "file"` with
null line/end_line/hunk_id, and disclose uninspectable contents in coverage.

Selected automatically for unfiltered reviews; an explicit focus filter may
exclude it and must disclose that exclusion. Code quality, runtime behavior and
commit-message quality are outside this lens.

Categories: `secrets`, `credentials`, `binary`, `os-files`, `generated`,
`merge-conflict`, `gitignore`, `large-file`.
