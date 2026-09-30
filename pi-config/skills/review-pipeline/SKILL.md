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

Parse the complete `$@` invocation with `parseReviewInvocation` in `command.mjs`
using `pipeline.json`; no substring-matched modes or free-form filters:

| Invocation | Routing | Target |
|---|---|---|
| `/review` or `/review parallel` | Automatic matching focuses, four-at-a-time | Current staged + tracked unstaged + untracked changes |
| `/review single` | One general reviewer | Current changes |
| `/review simplify` | One simplicity-focus reviewer | Current changes |
| `/review <focus-id> [scope]` | One named-focus reviewer | Current unless specified |
| `/review [parallel|single|focus-id] pr <url>` | Selected routing | Explicit PR URL |
| `/review [parallel|single|focus-id] branch` | Selected routing | Explicit branch comparison |
| `/review [parallel|single|focus-id] staged|unstaged` | Selected routing | Explicit narrower local layer |

`branch <focus-id>` and `pr <url> <focus-id>` remain accepted legacy forms.
Missing PR URLs, extra tokens and unknown/ambiguous aliases are input errors.
`general` is metadata for single mode, not an automatic ninth focus. Explicit
focus mode reports excluded focuses and labels the verdict **filtered scope only**.
Default current scope is not a synonym for branch comparison.

Gather complete evidence using the [evidence contract](contracts.md#evidence).
For default current scope, call `captureLocalEvidence` from `evidence.mjs` and
recheck `verifyLocalSnapshot` before dispatch and after review. Keep the distinct
index, tracked worktree, and untracked layers; never silently replace them with
`git diff HEAD`. For narrow local scopes exclude other layers explicitly.
Resolve the branch's actual comparison base; do not assume `origin/main` exists.
For PRs use `gh pr view <url> --json files,title,body,baseRefName,baseRefOid,headRefOid`
and `gh pr diff <url>`. If `gh` is unavailable, fetch equivalent complete metadata
and diff; a PR HTML page or truncated tool response is not equivalent evidence.
Pin and recheck base/head identities around collection. Record repo/cwd, scope,
refs, local snapshot hashes, changed files, and every hunk. Do not mix PR-head
evidence with an unrelated local checkout. No diff means “No changes to review”.
Unstaged scope excludes untracked files; disclose that boundary.

## 2. Select focuses

Read `pipeline.json`. Use the bundled `node validate.mjs select <input.json>`
helper with the packet's `changed_files` and parsed `filter` to record selection
and exclusion reasons (see [validation CLI](validation.md)). This helper performs
bookkeeping only: every selected review is still performed by an AI subagent.
Without a filter, select `always` focuses plus focuses whose
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
and `subagent({action:"models"})`. Require the canonical, executable native Pi
AI `reviewer`; external CLI/job runners and local validation scripts are not
reviewer substitutes.
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
review lens and categories. Each task contains: an absolute reference to its focus instructions, common report
contract/schema, repo/cwd/ref, evidence packet location or complete inline packet,
a statement that its complete assigned hunk/file ID inventory is in the packet, invocation UUID, digest, and the report-only boundary.
Reviewers do not orchestrate this pipeline or launch further reviewers.

Build the native launch with `buildReviewerLaunch` in `launch.mjs`, after
verifying an absolute policy-approved `packetRef`, a complete ID inventory, and
the resolved focus instructions. If `react-best-practices` is selected, first
call `loadPinnedReactRules('~/.agents/skills/vercel-react-best-practices')` from
`react-rules.mjs`; pass its returned object as `reactSkill` to the builder. Do
not launch that lens if this strict integrity check fails. The returned `expected`
manifest is frozen **before** dispatch; use it for reconciliation even if launches
fail.

For `single` or a named focus, call native `subagent` once with the returned
`subagentArgs`: `agent:'reviewer'`, `async:true`, `context:'fresh'`, inline
structured output, artifacts and the shared acceptance contract. `single` uses
`general` metadata; a focus uses its actual registry ID. No workflow script is
needed for one reviewer.

For parallel mode, statically validate the canonical [`dispatch.js`](dispatch.js)
workflow recipe with `action:'validate'` and then make **one** top-level call
with the builder's `subagentArgs`. It runs at most four fresh AI reviewer lanes
per wave (`max_concurrent_reviewers` is capped at four); each wave settles before
the next starts. On failure, preserve all settled sibling receipts and stop
before the next wave. The recipe is orchestration, not a reviewer or runner.
Neither path overrides agent model, thinking, tools or safety policy.

Reports return to the monitoring parent through `structuredOutput`; runtime-owned
files retain transcripts, metadata and workflow results. The recipe explicitly
sets each child to `output: false`, `outputMode: "inline"`, `artifacts: true` and
`acceptance: { level: "attested", report: "on" }`. The structured tool takes
`{ value: <review report>, acceptanceReport: <runtime acceptance evidence> }`;
`acceptanceReport` is a sibling of `value`, not a field in `report.schema.json`.
Use the runtime's acceptance instructions for that sibling. Reviewers must not
write report or log files. See [report delivery and logs](contracts.md#report-delivery-and-logs)
for the complete launch shape and persistence/recovery rules. When reconciling
the React lens, pass the validated `reactSkill.ruleIds` as `reactRuleIds`; every
React finding must cite one of those IDs.

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

Apply [validation, coverage and aggregation rules](contracts.md#reconciliation)
using the bundled `node validate.mjs reconcile <bundle.json>` CLI, not the separate
legacy OpenCode test helpers. See [bundle format](validation.md). Validate the
shared schema plus exact focus/invocation/digest and runtime identity. The first
pass identifies structurally valid candidates. The parent traces each candidate
against the frozen evidence, records an accept/reject decision with a reason,
and reruns reconciliation. Undecided candidates remain inconclusive; the script
cannot determine whether an AI finding is semantically true.
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
