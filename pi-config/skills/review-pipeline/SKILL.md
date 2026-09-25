---
name: review-pipeline
description: Use when reviewing PRs, branches, staged changes, or unstaged changes.
---

# Review Pipeline

One report-only review workflow per scope, with fresh instances of the predefined
`reviewer` agent applying distinct focuses. No independent second review workflow,
automatic fixes, commits, or implementation handoffs. Higher-priority user and
system instructions still apply. Return the report, then wait for explicit approval
identifying the findings or scope to fix.

## 1. Resolve scope and evidence

Parse arguments before selecting focuses:

| Invocation | Target | Optional focus filter |
|---|---|---|
| `pr <url> [focus]` | PR URL in argument 2 | argument 3 |
| `branch [focus]` | current branch | argument 2 |
| `staged [focus]` | index vs HEAD | argument 2 |
| `unstaged [focus]` | tracked working tree vs index | argument 2 |

Default scope is `branch`. Missing PR URL, extra arguments, unknown scope, or a
filter matching no focus is an input error, not a passing review. Filters match
focus ID or label by case-insensitive substring. An explicit filter replaces
automatic selection (including `always` focuses); report all excluded focuses and
label the result **filtered scope only**, never whole-change approval.

Gather complete evidence using the [evidence contract](contracts.md#evidence).
Resolve the branch's actual comparison base; do not assume `origin/main` exists.
For PRs use `gh pr view <url> --json files,title,body,baseRefName,baseRefOid,headRefOid`
and `gh pr diff <url>`. If `gh` is unavailable, fetch equivalent complete metadata
and diff; a PR HTML page or truncated tool response is not equivalent evidence.
Pin and recheck base/head identities around collection. Record repo/cwd, scope,
refs, local snapshot hashes, changed files, and every hunk. Do not mix PR-head
evidence with an unrelated local checkout. No diff means “No changes to review”.
Unstaged scope excludes untracked files; disclose that boundary.

## 2. Select focuses

Read `pipeline.json`. Without a filter, select `always` focuses plus focuses whose
`triggers.any_of` has a matching rule. Each rule requires **one same changed file**
to match both `path_patterns` and `extensions` when extensions are supplied.
Omitted extensions mean any extension. Test old and new paths for renames.

Patterns are case-sensitive POSIX globs against repository-relative paths:
`**/` matches zero or more directory segments, `*` matches within one segment,
and `**` spans segments. Normalize separators to `/`; do not use substring or
prefix matching. Thus `**/src/**` matches both `src/a.ts` and
`packages/client/src/a.ts`. Do not gate a focus on total changed-line counts:
small changes can still introduce bugs. Record each selection reason.

## 3. Preflight the predefined reviewer

Load `pi-subagents` guidance. Call `subagent({action:"list", capabilities:true})`
and `subagent({action:"models"})`. Require the canonical, executable `reviewer`.
Record its resolved **exact provider/model, thinking level and configuration
source**; verify that exact model exists in the current registry and matches any
operator-specified model constraint. An inherited parent-model default is not a
predefined reviewer model: stop and ask for agent configuration.

The agent definition owns model selection, tools, permissions, safety, redaction,
and trust policy. Inherit it unchanged. Do not define tool allowlists here, edit
agent configuration, load another profile, or pass model/thinking/tool overrides.
All focuses use that same predefined agent configuration. Never rotate models,
fuzzy-match a missing model, switch providers, downgrade, or escalate to another
agent/model. Quota, availability, or configuration errors are blockers—not
permission to select a fallback. If configuration changes during the run, stop
and mark affected results inconclusive; do not combine model variants.

Prepare evidence in accordance with the agent's safety policy before dispatch.
If required safe evidence cannot be provided, report the limitation rather than
inventing a weaker policy or silently bypassing it.

## 4. Dispatch once

Read `contracts.md`, `report.schema.json`, and each selected focus's `file` from
the registry. The shared contract is authoritative; focus files only define the
review lens and categories. Each task contains: focus instructions, common report
contract/schema, repo/cwd/ref, evidence packet location or complete inline packet,
assigned hunk/file IDs, invocation UUID, digest, and the report-only boundary.
Reviewers do not orchestrate this pipeline or launch further reviewers.

Use the canonical [`dispatch.js`](dispatch.js) raw workflow recipe. See
[dispatch inputs](contracts.md#dispatch-inputs). First statically validate it with
`action: "validate"`; then make exactly one top-level call with
`workflowScriptPath` set to its absolute path, `args`, explicit repository `cwd`,
`async: true`, and `context: "fresh"`. Set `globalConcurrencyLimit` to the
registry's `max_concurrent_reviewers` (hard ceiling 10). The recipe validates args
before mapping, batches `runs.all`, awaits its ordered results, and retains run
and invocation identities. It does not implement model or tool policy.

Yield for native async completion notifications. Do not poll or call `bg_wait`
just to wait for these children. Inspect actual child runtime model/thinking
metadata against the recorded preflight configuration before accepting results;
a reviewer echoing the expected model in prose is not runtime evidence.

For workflow, launch, provider, or tooling failure: stop further dispatch, preserve
available receipts/partial results, and report exact error/run/status/repo/cwd/
branch/ref. Mark undispatched and failed selected focuses inconclusive. Do not
silently retry, revive a review session, replace a reviewer, switch to CLI or
foreground execution, or emit a passing verdict. An operator-authorized rerun is
a new scope snapshot with fresh invocation IDs, still using the predefined agent.

## 5. Reconcile and report

Apply [validation, coverage and aggregation rules](contracts.md#reconciliation).
Validate the shared schema plus exact focus/invocation/digest and runtime identity.
An empty findings array is not sufficient for success. Missing, malformed, failed,
stale, truncated, or incomplete reports are inconclusive. Never invent findings
or claim hunks were reviewed merely because they were supplied.

Verdict precedence, using only validated findings:

1. Any `critical` or `important` finding → **Needs Work** (even with incomplete coverage).
2. Otherwise, any selected focus incomplete/inconclusive or output omitted → **Inconclusive**.
3. Otherwise → **Passes Review** (suggestions remain visible).

Always report coverage separately as **complete** or **incomplete**, with
selected/completed/inconclusive counts. A filtered pass applies only to the
explicit filter. Infrastructure-blocked runs must disclose the blocker even when
validated findings already establish Needs Work.

The final Markdown report contains, in order:
- Scope, filter/exclusions, repo/base/head or snapshot hashes, timestamp.
- Verdict and independent coverage status; blockers and exact failures.
- Every validated finding, grouped by severity: ID, focus provenance, file/line
  and side (or file-level location), issue, impact, confidence, proposed fix.
- Deduplicated strengths and per-focus summaries, including inconclusive reasons.
- Evidence: packet/diff hashes, reviewed/omitted files and hunks, run/invocation
  IDs, configured and observed model/thinking identities, limitations.
- Recommended next steps; explicit pause for user approval before any fixes.

Do not omit confirmed findings because they are inconvenient or numerous. If
output limits prevent complete reporting, disclose overflow, retain available
artifacts, and mark coverage incomplete. Never quietly apply a findings cap.
