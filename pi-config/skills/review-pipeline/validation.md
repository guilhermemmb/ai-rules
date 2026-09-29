# Pi review validation CLI

This CLI selects review lenses and validates reports. It never launches a reviewer,
reads source to invent findings, or substitutes scripts for AI review. Every
selected reviewer is a native Pi AI subagent: direct for single/focus, or via
`dispatch.js` in bounded four-at-a-time waves for parallel mode. The parent runs
this CLI through its shell; reviewer permissions stay read-only.

Invoke using the installed skill's absolute path:

```sh
node /absolute/path/to/review-pipeline/validate.mjs select selection-input.json
node /absolute/path/to/review-pipeline/validate.mjs reconcile review-bundle.json
```

The selector uses `pipeline.json`. Reconciliation uses that same registry and
`report.schema.json`, with a fail-closed validator for only the schema keywords
used by this contract: `$schema`, `title`, `type`, `additionalProperties`,
`required`, `properties`, `items`, `enum`, `minLength`, `pattern`, `uniqueItems`,
`minimum`, and `maximum`. Any unsupported schema keyword is an infrastructure
error, never a passing review. No private pi-subagents runtime source import or
`PI_SUBAGENTS_ROOT` dependency is required. Tests compare representative reports
against the installed runtime validator when available. Never substitute OpenCode
contracts.

Output is JSON on stdout. Reconciliation exits 0 for `Passes Review`, 1 for a
successfully evaluated `Needs Work` or `Inconclusive`, and 2 for malformed inputs,
missing runtime dependencies, or execution errors (diagnostic JSON on stderr).
Exit 1 is not itself an infrastructure failure; inspect the JSON verdict/coverage.
Store input/output artifacts under the canonical external planning reports path.

## Selection input

```json
{
  "filter": null,
  "changed_files": [
    {"id": "f1", "old_path": null, "new_path": "src/hooks/useDialog.ts", "status": "A", "binary": false}
  ]
}
```

Pass the packet's complete changed-file inventory, including both rename paths.
`filter` is null or a non-empty focus ID/label substring for the legacy selection
CLI. The `/review` command parser resolves exact focus IDs and aliases before
calling this helper. An explicit focus replaces automatic selection, including
always-on lenses. `general` is never automatically selected; its expected
invocation carries `applicableFocusIds` drawn from the triggered registry focuses,
so general findings can use their verified category union. Return selected IDs,
selection reasons and excluded IDs in the parent report; retain the filtered-scope
label. Use the selection result to build the complete expected-invocation manifest
before dispatch. Do not reconstruct expected invocations from successful results.

Rules use same-path glob AND extension matching. Accessibility includes TS/JS
hooks and focus/keyboard/accessibility/reduced-motion filenames. Correctness
includes behavior-bearing configuration formats and common build/env manifests.
These trigger review, not automatic findings. Each selected AI reviewer still
receives the complete packet. Categories are canonical in the registry; focus
Markdown explains the lens, examples and exclusions.

## Reconciliation input

```json
{
  "packet": {
    "packet_digest": "sha256:<64 lowercase hex characters>",
    "complete": true,
    "changed_files": ["<actual packet file objects>"],
    "hunks": ["<actual packet hunk objects>"]
  },
  "expected": [
    {"focusId": "correctness", "invocationId": "<dispatch UUID>", "runId": "<actual returned run ID or null if unlaunched>"}
  ],
  "configuredIdentity": {"model": "<exact provider/model>", "thinking": "<preflight level>"},
  "runtimeIdentities": {
    "<actual run ID>": {"model": "<observed runtime model>", "thinking": "<observed runtime level>"}
  },
  "results": ["<full dispatch result objects, not notification previews>"],
  "evidenceDecisions": []
}
```

Replace explanatory strings/arrays with actual data. The full packet is accepted;
its metadata needed here is the digest, completeness, files, and hunks. The parent
must independently verify frozen packet/diff bytes and refs before/after collection;
this CLI compares digest identities but does not recompute a digest from reserialized
JSON. Copy observed identity from runtime metadata, never from the AI report.
Suffix-form observed models such as `provider/model:medium` are accepted only when
both the exact model and thinking match preflight.

Copy every result from the workflow value (or settled-results emission after a
failed wave), retaining correlation fields. Preserve expected invocations for
undispatched lanes; missing results are inconclusive. Full logs and receipts stay
separate from this normalized bundle and remain referenced by the final report.

## Parent evidence decision pass

The first reconciliation checks schema, identities, runtime status, coverage,
categories and location bounds. It returns candidates but cannot prove their
semantic truth. For each candidate the parent verifies the actual changed-line
anchor, reachable defect/impact and remediation against frozen source evidence.
Record a decision:

```json
{"runId":"<actual run ID>","findingIndex":0,"decision":"accept","reason":"<specific source evidence and impact>"}
```

Use `reject` with an evidence-based reason for a false positive. Indices are
zero-based positions in the original report's `findings`, not the merged list.
Rerun reconciliation with all decisions. Duplicate/unknown/malformed decisions
are blockers; no decision is an unresolved candidate, not an implicitly accepted
or silently dropped finding. Decisions are parent attestations, not independent
runtime verification of source truth.

The output contains verdict, independent coverage, selected/dispatched/completed/
inconclusive counts, per-lane errors, candidates, accepted findings and rejected
findings with reasons. Exact location + issue + fix matches are conservatively
merged with all provenance and the highest supported severity. Other findings
stay separate rather than risking over-aggressive deduplication.

Validated critical/important findings produce `Needs Work` even when other lanes
are incomplete. Otherwise incomplete coverage or unresolved decisions produce
`Inconclusive`; only complete accepted results produce `Passes Review`. A successful
empty report still needs matching identities and complete file/hunk coverage.
Partial schema-valid reports may contribute evidence-accepted findings without
turning their lane into a pass. Failed runtime results are diagnostic only.

Publish the human-readable report using these results, including scope, filtered
exclusions, strengths, limitations and artifact references. Do not present the
JSON validator as an independent AI reviewer or as proof that tests/browser checks ran.
