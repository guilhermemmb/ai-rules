---
name: review-pr
description: AI rules/agent definition for review-pr.md
targets: ["opencode"]
---

# Review PR

The `orchestrator` dispatches exactly one `@reviewer-coordinator` using a
complete review packet and never dispatches `reviewer-*` lanes directly.
The coordinator ID is `reviewer-coordinator`; it is the sole coordinator and
must select and dispatch the exact ten read-only lanes: `reviewer-code`,
`reviewer-test`, `reviewer-errors`, `reviewer-types`, `reviewer-security`,
`reviewer-performance`, `reviewer-data-integrity`, `reviewer-accessibility`,
`reviewer-comments`, and `reviewer-simplifier`. Do not preload the coordinator
skill, select or directly dispatch lanes, run Phase B, aggregate findings, or
compute the verdict. Do not call `functions.skill` or silently fall back to a
partial direct-lane review.

The packet must include target descriptor, scope, complete relevant diff,
changed paths, diff metadata when available, implementer's report, task/plan
context, project guidelines, and available GitNexus evidence. The packet is
complete only when these fields are present and internally consistent for the
stated target; caller-supplied metadata does not replace the complete diff or
changed-path list. Missing or inconsistent packet fields fail closed: produce
a Degraded/inconclusive report and dispatch zero child lanes. Do not use an
implicit partial direct-lane fallback.

Use tagged policy requests for explicit overrides only; normalize textual
command input `all` to exactly `{"policy":{"kind":"full"}}` before policy
validation. No other textual alias is accepted. When no policy is provided,
materialize the target default as a tagged request:

```json
{"policy":{"kind":"auto"}}
{"policy":{"kind":"full"}}
{"policy":{"kind":"aspects","values":["security","errors"]}}
```

Current diff/task defaults to `auto`; entire branch, branch, and PR default to
`full`. Explicit tagged policy overrides the target default. The request object
must contain exactly `policy`; `auto` and `full` policy objects must contain
exactly `kind`, while `aspects` must contain exactly `kind` and a non-empty,
unique string-array `values`. Reject unknown kinds, extra fields, wrong types,
missing fields, empty or duplicate aspect lists, unknown aspects, `all` inside
an aspect list, and invalid combinations before any child dispatch. Accepted
aspects are `comments | tests | errors | types | security | performance |
data-integrity | code | simplify | accessibility`; textual `all` is never a
tagged kind and is invalid inside aspect values. Auto uses the coordinator's
trigger table. Full dispatches all nine Phase A concern lanes, then runs
`reviewer-simplifier` exactly once as sequential Phase B only for a non-empty
executable/source/config diff; docs-only records simplifier not-applicable.

GitNexus context is read-only evidence. The coordinator reads
`context/freshness`; stale, outdated, empty, partial, truncated, unknown,
ambiguous, degraded, error, timeout, or unmapped evidence is unusable, immediately
produces `final=unusable` and `fallback=native`, records `refresh=not permitted`,
marks Review Health Degraded/inconclusive when graph evidence is required, and
uses native RTK/OpenCode fallback without graph claims. It must not execute
repository-local analyze commands or any other Bash. After a fresh/usable initial status, run
the named `schema inspection` operation before any query/context. Any schema inspection,
query/context, process-resource, impact, or detect_changes result/status of
stale, outdated, empty, partial, truncated, unknown, ambiguous, degraded, error, timeout, or
unmapped immediately sets `final=unusable` and `fallback=native`, stops graph inspection, prohibits graph claims, uses native fallback,
and makes health inconclusive when graph evidence is required. An `unmapped`
status always requires Review Health Degraded/inconclusive. Normalize the
report as
`initial=<fresh/usable|stale|outdated|empty|partial|truncated|unknown|ambiguous|degraded|error|timeout|unmapped>;
refresh=not permitted; raw operation status=<not run|fresh/usable|error|timeout|stale|outdated|empty|partial|truncated|unknown|ambiguous|degraded|unmapped>; final=<fresh/usable|unusable>;
fallback=<none|native>; timing=<observed value|not observed>`. For any
unusable initial status, use `final=unusable` and `fallback=native`; operation
failures use the full raw operation status set shown above.

Resolve `REVIEWER_MAX_PARALLEL` as a trimmed complete integer: 1–3 are valid,
unset/empty/non-integer/zero/negative resolve to 3, and values above 3 clamp to
3. Phase A runs in canonical bounded background batches, waits for each batch,
and reconciles exact returned task session IDs before the next. Valid lane
results are retained when another lane fails, but failed, timed-out,
unavailable, malformed, incomplete, coordination, evidence, coverage, or
permission failures make Review Health Degraded/inconclusive. Phase B runs once
after all Phase A reconciliation and never concurrently. Require one-to-one
lane/session mapping; reject unknown, duplicate, missing, mismatched, or
cross-lane IDs and preserve affected raw responses. Attributed individual lane
failures are recoverable and permit later batches; batch completion failures or
impossible exact-session reconciliation are coordinator failures that stop all
subsequent dispatch.

Lane output is strict internal JSON. Validate every individual finding object in
each critical, important, and suggestions array for object shape, changed file,
numeric line, non-empty issue, confidence 0–100, and non-empty fix. Record
malformed entries as lane health errors with lane, array, reason, and discarded
count while retaining other valid findings. Caller-facing output is one inline
Markdown report, not JSON. The report includes target, packet completeness and
diff metadata, requested/resolved policy, triggered/skipped lanes with reasons,
raw/resolved concurrency, batches, Phase B decision, per-lane status, timing
quality, GitNexus initial/refresh/final/fallback status, Review Health, verdict,
deduplicated Critical/Important/Suggestions with source lane and changed
file:line/confidence/remediation, Strengths, Recommended Action, and any
finalization error.

Guard aggregation, deduplication, verdict, and Markdown rendering. A
finalization failure emits minimal Markdown with Review Health
Degraded/inconclusive, verdict `inconclusive`, the finalization error, and raw
valid findings/errors preserved where possible. If no coordinator response is
possible, treat it as failed and never direct-fallback.

Apply the deterministic verdict: packet/coordination/evidence/coverage/
lane/permission/finalization failure -> `inconclusive`; otherwise Critical ->
`blocked`; Important without Critical -> `changes-requested`; Suggestions only
-> `approved-with-suggestions`; clean healthy -> `approved`.

Preserve the coordinator's untrusted-content and read-only rules. Do not add
general GitHub or Bash access, dispatch another coordinator, or change
specialist review criteria. Do not run `gh pr comment` or any other GitHub
write/mutation command; print the final report to the terminal only.
