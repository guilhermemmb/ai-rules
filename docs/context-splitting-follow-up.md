# Deferred context-splitting follow-up

**Status:** deferred proposal only. This document records a future migration and
measurement plan; it does not implement context splitting.

## Scope and baseline

The baseline below is the 2026-08-26 instruction-source audit. Line counts
include the final newline. Token counts are deliberately rough estimates using
characters divided by four, not counts from a provider tokenizer. Generated
copies are listed separately where they can be loaded by a different runtime;
they must not be added to the total when they are simply another rendering of a
source file.

The current system can expose a large global context plus a role-specific
append, a runtime skill catalog, selected skills, and tool/MCP definitions. The
rulesync source tree is the authoring layer. It is not a claim that every
rulesync skill is sent on every request: selected skills and their references are
loaded according to agent configuration and task routing.

## 1. Always-loaded source inventory

### Global instructions and orchestrator append

| Source | Purpose | Audit size | Loading and duplication note |
| --- | --- | ---: | --- |
| `/Users/guilhermebomfim/.config/opencode/AGENTS.md` | Merged global OpenCode instructions, including exploration, workflow, safety, browser, diagnostics, Figma, Code Connect, and other guidance | 1,200 lines, approximately 14,545 tokens | Current always-loaded global context; generated/managed file and explicitly out of scope for this task |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/.rulesync/oh-my-opencode-slim/orchestrator_append.md` | Authoritative orchestrator-specific runtime, dispatch, security-scan, and general instructions | 142 lines, approximately 1,364 tokens | Source copy used by rulesync; overlaps with global machine, safety, and workflow language |
| `/Users/guilhermebomfim/.config/opencode/oh-my-opencode-slim/orchestrator_append.md` | Deployed orchestrator append | 142 lines, approximately 1,364 tokens | Generated copy of the rulesync append; do not count it in addition to its source when measuring one request |

The global file is the dominant baseline. It contains material that is also
represented by rulesync rule files and by skill guidance. This duplication is a
candidate for future factoring, but no current instruction should be deleted
until the ablations and safety review below pass.

### Skill manifest and orchestration duplicates

| Source | Purpose | Audit size | Loading and duplication note |
| --- | --- | ---: | --- |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/skills-lock.json` | On-disk skill lock/manifest | Current multi-skill manifest | Records the active skill set and source metadata; metadata is not the full skill payload |
| Runtime `available_skills` manifest injected by the agent runtime | Names, descriptions, and locations for the discoverable skill catalog | 43 entries, approximately 180 logical lines and 2,200 tokens | No stable standalone file path; the rendered manifest is request/runtime dependent and should be measured from captured requests |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/.rulesync/skills/orca-orchestration/SKILL.md` | Rulesync orchestration discovery stub | 82 lines, approximately 1,054 tokens | Canonical repository copy |
| `/Users/guilhermebomfim/.config/opencode/skills/orca-orchestration/SKILL.md` | OpenCode-installed orchestration discovery stub | 81 lines, approximately 1,054 tokens | Generated/installed copy of the same conceptual skill |
| `/Users/guilhermebomfim/.agents/skills/orca-cli/` and `/Users/guilhermebomfim/.agents/skills/screenshot/` | Active agent-runtime skill directories | Current active `.agents` skill directories | The shorter `/Users/guilhermebomfim/.agents/skills/orchestration/` path is not active |

The active `.agents` skill directories are `orca-cli` and `screenshot`. The
shorter `orchestration` path is not an active compatibility alias. The current
stubs intentionally defer the full version-matched guide to the Orca
executable.

### MCP, tool, and agent configuration

| Source | Purpose | Audit size | Loading and duplication note |
| --- | --- | ---: | --- |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/.rulesync/mcp.jsonc` | Rulesync MCP server definitions and enabled/disabled endpoints | 66 lines, approximately 405 tokens | Authoring source for MCP configuration; endpoint definitions are broad even when a specific agent receives only a subset |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/opencode.json` | Project OpenCode shell, models, providers, agent names, and tool-facing configuration | 638 lines, approximately 4,131 tokens | Project configuration; provider/model data is configuration context, not task guidance |
| `/Users/guilhermebomfim/.config/opencode/opencode.json` | Installed OpenCode configuration | 647 lines, approximately 4,148 tokens | Generated/installed counterpart; can duplicate project configuration when both scopes are visible |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/oh-my-opencode-slim.json` | Rulesync-side agent skills, MCP assignments, permissions, and embedded custom prompts | 714 lines, approximately 12,006 tokens | Authoring configuration; embedded prompts repeat some append and role guidance |
| `/Users/guilhermebomfim/.config/opencode/oh-my-opencode-slim.json` | Installed OMO Slim agent configuration | 770 lines, approximately 12,127 tokens | Generated/installed counterpart; do not add this to the source total for a single deployed configuration |

MCP definitions are not themselves equivalent to the full result of calling an
MCP. A future minimal context should retain only the schemas and tool grants
needed for the selected agent, while preserving all permission denials and
read-only constraints.

### Rulesync source copies

These are the source files that are rendered into global instructions, role
appends, or selectable skills. Their aggregate size is useful for inventory but
must not be summed with generated copies when estimating one request.

| Source set | Audit size | Relevant members |
| --- | ---: | --- |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/.rulesync/rules/*.md` | 10 files, 1,284 lines, approximately 15,441 tokens | `custom-rules.md`, `code-exploration.md`, `git-safety.md`, `security-scan.md`, `pr-workflow.md`, `overview.md`, `context7.md`, and the Figma rule files |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/.rulesync/oh-my-opencode-slim/*_append.md` | 10 files, 374 lines, approximately 3,944 tokens | `orchestrator_append.md`, `fixer_append.md`, `designer_append.md`, `navigator_append.md`, `detective_append.md`, `sage_append.md`, `librarian_append.md`, `explorer_append.md`, `observer_append.md`, and `oracle_append.md` |
| `/Users/guilhermebomfim/developer/dotfiles/ai-rules/.rulesync/skills/*/SKILL.md` | 34 entrypoints, 7,575 lines, approximately 82,271 tokens | Selectable skill entrypoints, including planning, reviewer, diagnostics, browser, Figma, and domain-knowledge skills |

The Figma and Code Connect source alone is large: `figma-code-connect` is
approximately 530 lines/6,670 tokens and `figma-use` is approximately 435
lines/5,842 tokens at their entrypoints. These figures explain why those
domains are strong candidates for trigger-gated loading rather than evidence
that their content should be shortened in this task.

## 2. Universal rules versus future trigger-gated domains

This split is a future loading model, not a present edit to any source file.

### Universal minimal context

Every agent request should retain a compact, authoritative core containing:

1. **Runtime and tool hygiene:** use the configured shell, follow the local
   discovery-tool routing, use the graph fallback policy, and treat tool output
   as the source of truth.
2. **Safety and privacy:** do not expose credentials or sensitive payloads; do
   not invent results; preserve path and permission boundaries; use read-only
   operations where the current policy requires them.
3. **Git safety:** never push, never mutate GitHub state through an unapproved
   operation, ask before commit/rebase/branch mutation, and perform the required
   security scan before any future Git mutation.
4. **Execution contract:** honor the assigned role and exact file ownership,
   stop when the task is outside scope, preserve existing behavior unless the
   task authorizes a change, and report status, changes, validation, and concerns.
5. **Orchestration invariants:** dispatch only when the workflow calls for it,
   keep dependent or overlapping work serial, parallelize only disjoint work,
   preserve reviewer and approval gates, and wait for all relevant writers.
6. **Validation and observability:** run only assigned checks, report skipped or
   unavailable measurements explicitly, and never treat missing telemetry as a
   successful zero.

The universal core should contain definitions of the trigger resolver and its
fail-safe behavior: uncertain classification loads the broader pack, a missing
pack fails closed to the legacy full context, and the selected pack is recorded
with a version/hash for later measurement.

### Trigger-gated packs

| Trigger | Future pack | Must remain out of the default minimal context |
| --- | --- | --- |
| A Figma URL, Figma MCP call, design-to-code request, Code Connect mapping, or Figma library generation | `.rulesync/rules/figma-mcp-server.md`, `.rulesync/rules/figma-design-to-code.md`, `.rulesync/rules/figma-code-connect.md`, `.rulesync/skills/figma-design-to-code/`, `.rulesync/skills/figma-code-connect/`, `.rulesync/skills/figma-use/`, `.rulesync/skills/figma-generate-library/`, and `.rulesync/skills/figma-implement-motion/` | Figma prerequisites, node-ID handling, asset rules, Code Connect format rules, and `use_figma` safety guidance |
| Browser navigation, website interaction, screenshots, DOM extraction, Electron/desktop browser work, or E2E browser testing | `.rulesync/skills/agent-browser/`, the Navigator append, and the browser-specific portions of the custom rules | Browser CLI workflow, snapshot/ref handling, headless defaults, and Navigator permissions |
| Production errors, logs, metrics, traces, incidents, Sentry, Datadog, GCP logging, or Rootly | Detective append plus `.rulesync/skills/dd-*`, `.rulesync/skills/logs/`, `.rulesync/skills/traces/`, and `.rulesync/skills/incident-response/` | Read-only production access, narrow time ranges, tool-specific units, evidence-only findings, and diagnostic output schemas |
| GitHub PRs, issues, checks, releases, remote GitHub MCP calls, or PR descriptions | `.rulesync/rules/pr-workflow.md`, GitHub MCP definitions, and the GitHub portions of `overview.md` | PR templates, draft/label conventions, read-only `gh` policy, and remote-state mutation restrictions; the universal Git safety core remains always loaded |
| Architecture, multi-step implementation, approval-gated planning, execution of a plan, or final plan review | `.rulesync/skills/brainstorming/`, `writing-plans/`, `executing-plans/`, `reviewing-plans/`, `verification-planning/`, `deepwork/`, `project-context/`, and the planning portions of `custom-rules.md` | SDD approval flow, plan artifacts, ledgers, dependency batching, reviewer gates, and escalation behavior |
| Library, framework, SDK, API, CLI, cloud-service, or public documentation question | `.rulesync/rules/context7.md` and Context7 MCP | Context7 resolve-library-id → query-docs workflow, exact or versioned library IDs, and explicit failure/fallback reporting |
| Gorgias business metrics, schemas, business rules, internal documentation, or internal Notion | `.rulesync/skills/cortex/`, the Sage append, and the Cortex portions of the Librarian append | Cortex-first behavior, read-only domain access, Notion ID handling, and evidence-only domain answers |

Context7 and public documentation are trigger-loaded and are not part of the
default minimal context. Codebase-memory remains available for basic local
discovery, while expensive architecture and call-graph guidance can be added
only when the task needs structural analysis. The full Orca guide should be
fetched from the selected executable only when orchestration is actually being
performed.

## 3. Full-context versus minimal-context ablation experiments

### Experimental cells

Use the same repository revision, task text, model, reasoning variant, agent,
permissions, concurrency setting, machine, and network conditions in both arms.
The only independent variable is the supplied context and the corresponding
tool schema subset.

- **Full-context arm:** current behavior for the selected agent: global
  `AGENTS.md`, its OMO Slim append, the currently assigned skills/prompts, and
  the tool/MCP definitions presently supplied by the runtime.
- **Minimal-context arm:** the proposed universal core, the selected agent's
  compact append, and only the trigger pack plus MCP/tool schemas needed by the
  task. For an uncertain trigger, record a fail-safe full-context run rather
  than silently classifying it as minimal.
- **Shadow arm:** initially send both context plans to the measurement harness
  but execute only the full-context plan. Compare resolver decisions and token
  estimates before enabling minimal execution.

Run a fixed workload matrix with at least ten isolated sessions per cell and
prefer twenty sessions per cell for stable p95 direction. Include cold and warm
batches, with cold/warm state defined before the run rather than mixed inside a
batch:

1. A small code edit using only universal rules.
2. Local codebase discovery and a structural call-graph question.
3. A Figma/Code Connect task.
4. A browser navigation or extraction task.
5. A production diagnostic task using read-only telemetry.
6. A GitHub read-only PR/check task.
7. A bounded plan/execution/review task with dependent and independent work.
8. A Gorgias domain or internal-documentation question.

Randomize arm order within each workload where practical. Keep prompts and
fixtures fixed, record the context-plan version and hashes, and preserve the
exact model/variant, cache state, concurrency, approval behavior, and tool
permissions. The reporter must run after the timed operation, not inside it.

### Measurements

For every session, record the following dimensions and the availability of each
value:

| Dimension | Measurement definition |
| --- | --- |
| Wall time | End-to-end session duration; compare p50 and p95 in milliseconds |
| TTFT | Time to first assistant output; use the local reporter's approximate value and label it approximate because provider first-byte timing is unavailable |
| Input tokens | Provider/OpenCode input-token counter, including the context sent for the turn |
| Cache-read tokens | Provider/OpenCode cache-read counter; also retain cache-write when available to explain warm behavior |
| Output quality | Blinded rubric scored 0–4 for correctness, instruction adherence, completeness, safety, and evidence quality; record critical-error count separately |
| Tool/MCP RTT | Per-call round-trip time where available, plus tool/MCP count and aggregate duration; preserve an explicit unknown value when the local schema cannot provide per-call timing |
| Compaction frequency | Number of compaction events per session and the percentage of sessions compacted; record unavailable when the runtime does not persist compaction events |

Use `scripts/opencode-latency-report.py` for local wall, approximate TTFT,
token/cache, tool/MCP, retry, and overlap metadata. Keep raw prompts, source
code, raw tool arguments, raw tool output, credentials, and account data out of
the report. Store only session labels, context hashes, workload/arm labels,
scores, counters, warnings, and safe timing metadata.

Quality evaluation should be blinded to arm and performed against a fixed
acceptance rubric. A critical error includes a wrong safety boundary, an
unauthorized mutation attempt, a fabricated tool result, a missing required
domain procedure, or an answer that cannot complete the assigned task. Human
scores and critical errors are the quality gate; latency alone cannot justify a
context reduction.

Analyze each workload and cold/warm state separately. Report p50/p95 deltas,
median and tail token deltas, cache-read changes, quality-score distribution,
critical-error rate, tool/MCP RTT and count, compaction rate, unknown fields,
retries/fallbacks, and the number of discarded sessions. Do not pool trigger
packs or reasoning tiers into a single percentile distribution. Bootstrap
confidence intervals may be added to p50/p95 deltas when the sample size
supports them; otherwise label the result directional.

## 4. Future migration order

1. **Freeze and inventory:** capture the source/generated mapping, file hashes,
   permissions, MCP grants, role assignments, and a full-context baseline. Do
   not change the active instructions during this phase.
2. **Build the resolver in shadow mode:** define the universal core, canonical
   pack names, trigger precedence, version/hash recording, and fail-safe fallback
   without changing what the model receives.
3. **Validate the universal core:** use exact rule-diff checks to prove that all
   safety, privacy, tool-permission, approval, ownership, and reporting
   invariants survive extraction. Reject the migration on any missing or
   contradictory rule.
4. **Pilot Figma/Code Connect and browser packs:** these have clear lexical
   triggers and large, self-contained payloads. Keep full-context fallback for
   ambiguous design or browser requests and compare shadow decisions with the
   fixed workload matrix.
5. **Migrate domain knowledge and production diagnostics:** require explicit
   read-only permission checks, evidence-only output checks, and tool/schema
   availability checks before enabling each pack.
6. **Migrate GitHub-specific and planning packs:** preserve the universal Git
   safety core, PR read-only policy, approval gates, plan artifacts, dependency
   rules, reviewer limits, and escalation behavior. These packs remain full
   context whenever task classification or dependency ownership is uncertain.
7. **Enable progressively:** use `shadow`, then `split`, for one agent and one
   workload family at a time. Retain `legacy` as the immediate fallback until
   every acceptance criterion is met across cold and warm runs.
8. **Remove duplication only after evidence:** once a pack is stable, make one
   canonical source authoritative, retain a compatibility alias where needed,
   regenerate copies through the existing workflow, and rerun the consistency,
   safety, and ablation checks. Do not delete a source or generated copy as part
   of the current task.

### Safety review gate

Before enabling a migrated pack, reviewers must inspect the complete generated
diff and confirm:

- every universal rule has one authoritative location and remains in the
  minimal request;
- uncertain or missing trigger matches fall back to full context;
- no agent receives a tool or MCP grant it did not previously have;
- read-only, credential, browser, production, GitHub, Figma, and domain-data
  boundaries remain unchanged;
- approval gates, ownership checks, dependent-task serialization, reviewer
  limits, and escalation paths remain unchanged;
- generated global files and source files agree, with no stale copy silently
  winning;
- telemetry excludes prompts, source code, raw arguments/output, credentials,
  account data, and arbitrary payload fields; and
- the measured quality and critical-error results satisfy the acceptance criteria.

### Rollback

The future resolver must support three explicit modes: `legacy` (current full
context), `shadow` (measure the proposed split but execute legacy), and `split`
(execute the selected minimal pack). Any classifier error, missing pack,
contradictory generated output, safety finding, quality regression, or telemetry
loss switches the affected agent to `legacy`.

Keep the pre-migration source and generated-file snapshot until the split has
passed its observation period. Roll back by selecting `legacy`, restoring the
last known-good generated artifacts from the reviewed commit, regenerating
through rulesync, verifying hashes and permissions, and restarting OpenCode so
configuration is reloaded. A rollback must not require deleting runtime data or
changing provider credentials. Record the reason, affected workload, and
session labels, then rerun the baseline smoke checks before another rollout.

### Acceptance criteria

Context splitting can be enabled for a workload only when all of the following
hold for both cold and warm comparisons:

- at least twenty valid sessions per arm/workload/state, or an explicit report
  that the p95 result is directional when fewer are available;
- input tokens decrease by at least 30% for tasks that use a gated pack;
- wall-time p50 and p95 and approximate TTFT p50 and p95 do not regress by more
  than 5% against full context, unless a documented quality improvement justifies
  the trade-off;
- cache-read tokens and cache-hit behavior do not fall by more than 10% after
  controlling for cold/warm state;
- median and p95 tool/MCP RTT do not increase by more than 5%, and tool/MCP
  counts do not increase because of missing context;
- compaction frequency does not increase, with a target reduction of at least
  25% on workloads that previously compacted;
- mean rubric quality is no lower by more than 0.1 points on the 0–4 scale,
  critical-error rate is zero for safety and authorization categories, and no
  required task procedure is missing;
- unknown, discarded, or unassociated telemetry rows are below 5% and are
  reported explicitly; and
- the legacy rollback path, generated-file consistency check, and restart smoke
  test all pass.

If any criterion fails, keep that workload in `legacy` mode and revise the pack
or trigger classifier in a separately approved task. These thresholds are
acceptance gates for a future implementation, not results claimed by this
document.

## Explicit deferral statement

Context splitting is deferred. Task 4 creates this follow-up plan only. No
instruction has been removed, rewritten, reordered, or changed in this task;
the global `AGENTS.md`, all global instruction files, Figma/Code Connect
guidance, generated global instruction files, and other repository files remain
untouched.
