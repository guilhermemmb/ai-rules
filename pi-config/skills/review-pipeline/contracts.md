# Review Pipeline Contracts

## Evidence

The parent collects one immutable snapshot before dispatch. Evidence storage and
handling follow the predefined agent policy; this document defines identity and
coverage, not a separate security policy. Keep artifacts outside the reviewed
repository under its canonical planning reports directory when persistence is
needed. Complete inline evidence is also valid.

For default `current` scope, call `captureLocalEvidence({repo, scope:'current'})` in
`evidence.mjs`. It captures separate index, tracked worktree and untracked layers,
including opposing changes that cancel in a net HEAD-to-worktree diff. Explicit
`staged`/`unstaged` scopes use the same collector with only the selected tracked
layer; neither includes untracked files. Recheck with `verifyLocalSnapshot(packet)`
before dispatch and after review. Any incomplete content or changed snapshot
prevents a whole-change pass. Keep the packet's exact serialized bytes when
storing it; `packet_digest` hashes `JSON.stringify(packet)` before that field is
added. Preserve layer-specific patches and hashes, not just a net diff.

For branch scope, resolve the upstream/base with the user or repository metadata,
then capture `git diff --no-ext-diff --no-textconv <base>...HEAD` and its merge-base
and head SHAs. For staged use `git diff --cached --no-ext-diff --no-textconv`; for
unstaged use `git diff --no-ext-diff --no-textconv`. Collect NUL-delimited changed
paths/status separately to support spaces, renames, additions and deletions.
Record binary files even when no textual hunks exist. File lists from paginated
or bounded tools must be fully retrieved before declaring evidence complete.

Packet fields:

| Field | Meaning |
|---|---|
| `scope`, `scope_detail`, `filter` | Parsed request; filter null when absent |
| `repo`, `cwd`, `base_ref`, `base_sha`, `head_sha` | Exact target and identities; unavailable values explicitly null |
| `snapshot_id`, `layers` | SHA-256 of local HEAD and selected layer hashes; ordered `{name, sha256, paths}` entries for index, worktree, untracked as applicable |
| `diff_sha256`, `packet_digest` | Diff bytes hash; SHA-256 of UTF-8 JSON packet before adding `packet_digest` |
| `changed_files` | `{id, old_path, new_path, status, binary}` for each changed file; absent rename side null |
| `hunks` | `{id, file_id, old_start, old_count, new_start, new_count, content_ref}` |
| `full_diff_ref` | Absolute artifact path readable by reviewer, or complete inline diff |
| `complete` | True only when complete evidence was acquired, not merely a summary |
| `limitations` | Missing metadata, excluded untracked files, policy-redacted content, unavailable binaries, etc. |

Assign stable file IDs and global hunk IDs before truncating any preview. Persist
the exact serialized packet whose digest was computed; do not recompute from
reformatted JSON. Verify refs/diff hashes before and after collection; if they
change, rebuild the snapshot before dispatch. Recheck after review and disclose
staleness; do not claim the current working tree or PR head passed if it changed.

All selected focuses assess all captured changed files/hunks through their own
lens, even when one triggering file caused selection. Supply every focus the
complete ID inventory. A preview may be short, but must link to accessible full
content by hunk ID. Reading only a preview cannot satisfy coverage. If a reviewer
cannot retrieve content using its predefined tools, it reports omitted IDs and
errors; do not enlarge its permissions. For binary/file-only changes, review
metadata where sufficient and explicitly record any uninspectable content.

## Dispatch inputs

`dispatch.js` is a pi-subagents **workflow body**, not a Node CLI. Read its source
and use `subagent` with `workflowScriptPath`; do not copy an unvalidated ad hoc
script or expect filesystem access inside the workflow sandbox.

Build the call with `buildReviewerLaunch` from `launch.mjs` using the parsed
invocation, resolved focuses, policy-approved absolute packet reference/digest,
assigned file/hunk IDs, focus texts, schema and cwd. Freeze its `expected`
manifest before launch. For `single`/named-focus it returns one direct native
`subagent({agent:'reviewer', ...})` with the same child output/acceptance policy;
only parallel uses `dispatch.js` and the following bounded plain-JSON `args`:

```json
{
  "maxConcurrency": 4,
  "packetDigest": "sha256:<frozen-packet-hash>",
  "reportSchema": "<replace with the parsed report.schema.json object>",
  "lanes": [
    {
      "focusId": "correctness",
      "invocationId": "<new UUID>",
      "task": "<focus instructions + shared contract/schema + repo/ref + packet reference + full assigned ID inventory + output requirements>"
    }
  ]
}
```

Use the registry's concurrency, not a second hardcoded policy. `reportSchema`
above is explanatory: the real value must be the JSON object, never a path or
string. Freeze arguments after construction. Model/thinking/tool policy is NOT
an argument; the runner resolves the predefined `reviewer` agent. Record its
preflight configuration outside the child report and compare actual runtime
metadata for each completed child. Missing runtime evidence is inconclusive.

No raw sensitive content belongs in persisted args; use policy-approved evidence
references. A complete inline packet is permitted only when policy allows it and
the runtime's bounded args limit is respected.

For a direct review, normalize the one returned native run to the same result
shape as a workflow row (`key`, `focusId`, `invocationId`, `packetDigest`, `runId`,
`ok`, `structuredOutput` and diagnostic references). The parent supplies the
frozen correlation fields; compare the real runtime identity and report fields
before accepting it. Never infer a passing report from a successful run flag.

The recipe retains each `runs.all` result alongside its focus, invocation and
packet digest. Read `structuredOutput` as the report, not the run success flag
or `.output` alone. Preserve outputReference/outputPathMapping/artifactPaths
where returned by the runtime. If structured output is unavailable, reconcile as
inconclusive rather than treating absent findings as an empty array. The recipe
only dispatches and preserves results; the parent performs the checks below.

## Report delivery and logs

The parallel parent launch uses this shape (substitute actual paths and prepared
args; direct mode uses the builder's one reviewer call):

```js
subagent({
  workflowScriptPath: "<absolute skill path>/dispatch.js",
  args: preparedArgs,
  cwd: "<reviewed repository>",
  async: true,
  context: "fresh",
  globalConcurrencyLimit: 4, // pipeline.json.max_concurrent_reviewers
  outputMode: "inline",
  artifacts: true,
  output: "<canonical planning reports>/<unique review run>/workflow-result.md"
});
```

The optional top-level `output` saves the runtime's workflow result text, not a
JSON report: use `.md`. Its parent directory must exist. Omitting it uses the
runtime's default artifact location. It does not replace inline delivery.
Per-child `output: false` prevents aggregate-derived child file requirements;
`outputMode: "inline"` prevents inherited file-only delivery. `artifacts: true`
retains runtime-owned transcripts, metadata and structured-output captures without
requiring reviewer filesystem writes. No tool or agent-policy expansion is needed.

Use the returned `structuredOutput` as the review payload. To satisfy attestation
without violating the strict schema, call the runtime's `structured_output` tool
with `{ value: <schema-valid review>, acceptanceReport: <acceptance evidence> }`.
The dispatcher explicitly requests `acceptance: { level: "attested", report: "on" }`;
the runtime describes and validates the acceptance evidence separately. Do not add
`acceptanceReport` to the review value or replace findings with acceptance prose.
Attestation is not proof of tests or coverage: the parent still validates both.

Each settled wave emits compact progress: settled/total counts, lane identities,
status/error and runtime artifact references. Full reports return once in the
workflow value. A failed wave emits all settled results before stopping so the
parent can recover partial evidence. These emissions are persisted progress, not
an extra child-completion wake mechanism; use native async notifications.

Keep full transcripts in files rather than flooding parent context. Retain actual
`asyncId`/`asyncDir`, receipt/status paths and each child's artifact references in
the final report; never invent artifact filenames. Async notifications are previews.
After completion, retrieve the full workflow value from its result/status artifact
when needed; recover partial results from workflow emissions on failure. If any
preview or result is truncated, read the full referenced artifact before reconciling.
Missing artifacts remain an explicit limitation, never an empty passing report.
Runtime session artifacts are subject to retention cleanup; archive the final
validated report and evidence manifest under the canonical planning reports path
for long-term use. Do not copy sensitive raw transcripts outside approved storage.

## Reconciliation

`report.schema.json` is the single structural schema for every focus. Pass it as
`outputSchema` and include its field requirements in the reviewer task. Reviewers
return the schema through the runtime's structured output mechanism. No separate
focus-specific envelope and no prose-only verdict replace it. Run the bundled
[Pi validation CLI](validation.md) for mechanical checks, then record the parent's
source-evidence decisions and rerun it before publishing a final verdict. Its
schema validator is the installed pi-subagents implementation, so a missing or
incompatible runtime is a blocker rather than a weaker validation fallback.
Review content still comes exclusively from the predefined AI reviewer subagents.

For each expected invocation:
1. Require a successful runtime result and schema-valid report. Validate schema
   even for recovered artifact reports; never coerce missing fields to defaults.
2. Match exact `focus_id`, `invocation_id`, `packet_digest`, run mapping, and
   actual model/thinking identity. Reject duplicates, unexpected invocations,
   reports for an older snapshot, or mismatched focus IDs.
3. `success` must be true, `errors` empty, `findings_omitted` zero. Coverage arrays
   must contain only assigned IDs, no duplicate IDs or reviewed/omitted overlap,
   and their union must equal the assigned inventory. Complete means all files
   and hunks reviewed, none omitted. Unknown IDs or unaccounted IDs are invalid.
4. Validate every finding against actual evidence: changed file, correct side and
   line range, existing hunk when applicable, concrete issue/impact/fix, confidence
   in [0,1], and a category listed in that focus's `pipeline.json` `categories` array. Findings must be introduced or
   made reachable by this change, not unrelated pre-existing issues. Context may
   support reasoning; anchor the finding to a changed line or deletion.
5. `side: "new"` uses new-path line numbers; `"old"` uses old-path line numbers for
   deletions. `"file"` is only for file-level/binary findings and requires null
   line, end_line and hunk_id. Non-file findings need positive line/end_line,
   end_line >= line, and a real hunk_id. Do not fabricate line 1 for binary files.

A failed/incomplete focus never becomes passed because findings are empty. Keep
schema-valid, individually evidence-validated findings from partial reports,
label them partial, and keep that focus inconclusive. Malformed/unmatched reports
are diagnostic artifacts, not trusted findings. Distinguish selected, dispatched,
completed, and inconclusive counts; unlaunched selected focuses are inconclusive.

## Severity and aggregation

Shared impact rubric (all focuses):
- **critical**: demonstrated high-impact production failure, exploitable security
  issue, data loss/corruption, or loss of essential functionality/accessibility.
- **important**: concrete actionable defect/regression or material validation gap
  with explained impact; not merely a stylistic preference.
- **suggestion**: non-blocking simplification, convention alignment, or hardening.

Focus checklists are investigation prompts, not automatic findings. Missing
memoization, JSON.parse, duplicated components, missing tests, or naming alone do
not establish critical severity. Explain the reachable failure, affected users,
or material risk. Do not infer a security vulnerability without an attack path.

Merge only findings with the same location, root cause and proposed remediation;
do not collapse unrelated issues sharing a line. Preserve all contributing
focus/invocation IDs, evidence and meaningful fix alternatives. Use the highest
supported impact severity, not a vote or an average confidence. Record conflicts
and the parent's evidence-based resolution. Assign stable final finding IDs.

Verdict: any validated critical/important finding → Needs Work; otherwise any
missing required coverage or omitted finding → Inconclusive; otherwise Passes
Review. Report coverage independently, so actionable partial findings remain
visible without claiming full review. Suggestions do not block; explicit filters
limit the verdict to selected focuses.

## Maintenance verification

Run `node --test scripts/test_pi_review_*.mjs` from the repository root for Pi
argument forwarding, focus selection, dispatch and reconciliation fixtures.
Run `python3 -m unittest discover -s scripts` for other repository checks; its
legacy review-contract tests target OpenCode, not this Pi pipeline. The dispatch suite also checks the installed
pi-subagents structured-tool boundary when present (override its package path
with `PI_SUBAGENTS_ROOT`); report a skipped runtime check explicitly. Static runtime validation:
`subagent({action:"validate", workflowScriptPath:"<absolute skill path>/dispatch.js", args:<prepared args>})`.

Skill behavior scenarios (simulate, do not launch nested reviewers): configured
reviewer disagrees with a legacy model hint; unavailable configured model under
deadline pressure; one passed lane plus one timeout; PR URL without a filter;
one-line dependency manifest; one-line auth change; truncated evidence with empty
findings; partial report with an important issue; duplicate IDs; filtered review;
file-only binary finding; eight selected lanes with four-per-wave dispatch;
parent file-only defaults; strict review schema with acceptance evidence; failed
first wave with successful sibling evidence. Expected: inline parent reports,
runtime-owned diagnostic files, acceptance beside the review value, no later wave
after failure, no substitutions, explicit scope, security
coverage, correct identities, incomplete coverage never passes, and agent-owned
safety unchanged. Preserve baseline and post-change observations in external
planning reports; do not claim mock-run tests prove live provider compatibility.
