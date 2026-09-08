# Workflows

Operational workflows for the `ai-rules` system: how work is sized and planned,
how agents discover context and delegate, how implementation and review
pipelines run, and how the workspace and deployment lifecycle is owned.

> **Status labels used in this document:** `Current` = implemented in tracked
> source; `Validated` = verified by the repository validator/smoke scripts;
> `Observed` = recorded from a runtime probe; `Proposed` = recommended but not
> implemented. Where source and installed artifacts can differ, the text says so
> explicitly instead of claiming alignment.

The authoritative source for each workflow is linked inline. This document
summarizes and points at them rather than duplicating policy text. The full
task-sizing flowchart and agent-usage matrix live in
[`sdd-workflow.md`](./sdd-workflow.md).

---

## 1. T-shirt sizing and the SDD decision flow

Every request is first evaluated and reported as a
`T-shirt size: XS | S | M | L | XL` with a short rationale. The selection
determines the approval gates, planning artifacts, and review requirements.
Source: [`.rulesync/rules/custom-rules.md`](../.rulesync/rules/custom-rules.md).

| Size | Definition | Approval | Artifact | Review |
| :--- | :--- | :--- | :--- | :--- |
| **XS** | One obvious, isolated, reversible edit | None — dispatch immediately | None | None |
| **S** | Small local work, established patterns | One approval of a merged plan | One merged SDD + implementation plan | One automatic post-implementation gate |
| **M** | One cohesive bounded outcome across related files | One approval of a merged plan | One merged SDD + implementation plan | One automatic post-implementation gate |
| **L** | Multi-area / cross-system, or material uncertainty | Separate spec approval, then plan approval | Full SDD: spec + plan + ledger | Required per-task review; optional final review |
| **XL** | Architecture, migration, security/data-integrity, production-impact, external dependency | Separate spec approval, then plan approval | Full SDD: spec + plan + ledger | Required per-task review; optional final review |

### XS

Immediate dispatch to `@fixer` (code) or `@designer` (UI/UX). No approval, no
planning artifact, no SDD, no reviewer.

### S / M

One concise **merged** SDD + implementation plan, written to
`~/developer/planning-docs/{{repository-name}}/.planning/plans/`. Present it
once, wait for one approval, then dispatch implementation to `@fixer` (code) or
`@designer` (UI/UX). Exactly one post-implementation review gate runs
automatically through the OpenCode `review-pipeline`.

S/M must **not** create a separate spec, load `executing-plans`, create a
ledger, run a per-task review loop, or prompt the user to choose whether to
review. The review gate is required, not optional.

### L / XL

Full Spec-Driven Development:

1. **Brainstorming** — `@explorer` (codebase recon), `@librarian` (external
   research), `@oracle` (architecture assessment), `@designer` (UI sections).
   Show a **separate** design/spec and get approval before writing the plan.
   Spec lands in `~/developer/planning-docs/{{repository-name}}/.planning/specs/`.
2. **Writing plans** — load `writing-plans`; produce the implementation plan in
   `~/developer/planning-docs/{{repository-name}}/.planning/plans/`; get plan
   approval.
3. **Executing plans** — load `executing-plans`; create a ledger; dispatch fresh
   specialists per task with dependency-aware batching and per-task review.
4. **Reviewing plans** (optional) — the final comprehensive review runs only
   after **explicit user opt-in**.

### SDD artifact persistence

All SDD artifacts live **outside** the working repository at
`~/developer/planning-docs/{{repository-name}}/.planning/`:

- `specs/` — design docs
- `plans/` — implementation plans
- `ledger-<plan>.md` — execution ledgers
- `reports/` — per-task implementer reports

Source: [`custom-rules.md`](../.rulesync/rules/custom-rules.md) and
[`README.md`](../README.md#sdd-artifacts--developerplanning-docsrepository-nameplanning).

---

## 2. Discovery and delegation

### Discovery routing: RTK/native

Native RTK/OpenCode tools are authoritative for exact local inspection and
repository work. Source: [`.rulesync/rules/code-exploration.md`](../.rulesync/rules/code-exploration.md).

| Task | Tool |
| :--- | :--- |
| Exact string / symbol / literal / log search | `rtk grep` |
| Known-path localized read / signature | `rtk read` |
| File discovery by pattern | `rtk find` |
| Dynamic templates, macros, non-AST text | `rtk grep` / `rtk read` |
| Definitions, references, implementations, diagnostics | RTK/native OpenCode tools |
| Architecture and dependency reasoning | Native source inspection and task context |

Use native RTK/OpenCode tools for repository reconnaissance, dependency reasoning,
review inputs, and exact edits. Do not use unproxied `cat` / plain `grep` / `ls`
for discovery output.

RTK is also an OpenCode plugin that transparently rewrites ordinary commands
(`git status` → `rtk git status`). Explicit discovery subcommands are `rtk grep`,
`rtk read`, and `rtk find`.

### Agent delegation map

Intent-to-agent routing. Models are `Current` as declared directly in
[`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json), the sole model
configuration. Provider availability remains cataloged in `opencode.json`.

| Intent | Agent | Notes |
| :--- | :--- | :--- |
| Master delegation & coordination | Orchestrator | Default agent; manages review packets and the on-demand `review-pipeline` |
| Strategic/architecture decisions, escalation | Oracle | Also adjudicates failed review loops |
| Codebase reconnaissance | Explorer | RTK/native discovery |
| External/public research, docs | Librarian | Context7, websearch, Linear, Cortex |
| UI/UX implementation & design | Designer | Native tools + Figma skills; no code-intelligence MCP |
| Scoped code implementation | Fixer | Native tools; hard `Files` allowlist, no architecture decisions |
| Visual analysis | Observer | Auto-routes images from Orchestrator |
| Browser automation | Navigator | `agent-browser` CLI via Bash only |
| Production diagnostics | Detective | `pup`/`gcloud` via Bash, read-only |
| Gorgias domain knowledge | Sage | Cortex MCP, read-only |
| Review coordination (OpenCode) | Orchestrator | Loads `review-pipeline`; selects, batches, reconciles, aggregates, and computes the verdict for 10 read-only lanes |

See the [Agent Pantheon in the README](../README.md#agent-pantheon) and
[`agents-overview/`](../agents-overview/README.md) for the interactive view.

**Delegation guardrails** (source:
[`custom-rules.md`](../.rulesync/rules/custom-rules.md)):

- Notion → `@sage` (internal/Gorgias) or `@librarian` (public); never in-browser.
- Sentry / `pup` / `gcloud logging` → `@detective` only.
- Browser / `agent-browser` / `chrome-devtools-mcp` → `@navigator` only.

---

## 3. Fixer pipeline

The Fixer is a bounded implementation specialist. Source:
[`.rulesync/skills/fixer/SKILL.md`](../.rulesync/skills/fixer/SKILL.md).

### Handoff contract

Every fixer dispatch carries: `Goal`, `Files`, `Steps`,
`Interfaces/Constraints`, `Validation`, and optional `Stop Conditions`. Missing
required fields → return `NEEDS_CONTEXT`.

### Write-set allowlist

`Files` is a **hard write allowlist**, not a suggestion. The fixer may create,
modify, or delete only the exact paths listed there, and must not write
generated outputs, lockfiles, reports, planning artifacts, or temp files unless
explicitly listed. Overlap with another active task, a stale path, or ambiguous
ownership → stop and return `NEEDS_CONTEXT` or `BLOCKED`.

> `Current`: OpenCode exposes no dynamic per-task filesystem ACL, so the
> allowlist is **cooperative prompt enforcement** backed by the orchestrator's
> changed-path reconciliation. The fixer must never claim runtime ACL
> enforcement that was not observed.

### Bounded concurrency and reconciliation

Source:
[`custom-rules.md`](../.rulesync/rules/custom-rules.md) and
[`executing-plans`](../.rulesync/skills/executing-plans/SKILL.md).

- OpenCode may dispatch at most **3** independent `@fixer` children per
  implementation batch, each with `background=true`. This cap is independent of
  the reviewer concurrency cap.
- A batch is eligible only when tasks have **complete, disjoint** write sets and
  no interface, shared-state, or ordering dependency. Any overlap, ambiguity,
  shared resource, generated output, lockfile, or explicit sequencing
  **serializes**.
- The orchestrator waits for every child in the same batch and reconciles each
  result with `task_result` using the **exact returned session ID** — never an
  alias, title, or ordering assumption.
- Each `DONE` child passes its own per-child review gate before its dependents
  are released. `NEEDS_CONTEXT`, `BLOCKED`, timeout, failure, missing, or
  malformed results hold dependents and are surfaced.

### Escalation and status

Fixer returns only `DONE` / `NEEDS_CONTEXT` / `BLOCKED`. Escalate immediately on
stale paths, missing acceptance criteria, out-of-allowlist changes, or
unrelated multi-concept scope. Fixers never run `git commit` / `git push`
autonomously (see [`git-safety.md`](../.rulesync/rules/git-safety.md)).

---

## 4. Reviewer pipeline

Source: the on-demand
[`review-pipeline` skill](../.rulesync/skills/review-pipeline/SKILL.md), its
canonical [`pipeline.json`](../.rulesync/skills/review-pipeline/pipeline.json),
and the [`review-pr` command](../.rulesync/commands/review-pr.md). The registry
is the single source of truth for lane IDs, order, triggers, phases, policy
aliases/defaults, packet/result fields, and verdict precedence; this page does
not reproduce a competing registry.

### Orchestrator ownership

At a review boundary, the orchestrator loads the skill and is the review
manager. The active topology is `orchestrator -> reviewer-*`: it validates the
packet, normalizes policy, selects lanes, directly dispatches fresh read-only
leaf sessions, reconciles exact sessions, aggregates findings, computes the
verdict, and renders one caller-facing Markdown report. The skill is not
preloaded into ordinary sessions, and there is no intermediary review agent.

The ten registry lanes are `reviewer-code`, `reviewer-test`, `reviewer-errors`,
`reviewer-types`, `reviewer-security`, `reviewer-performance`,
`reviewer-data-integrity`, `reviewer-accessibility`, `reviewer-comments`, and
`reviewer-simplifier`. Their triggers and canonical order remain in
`pipeline.json`; do not duplicate those definitions here.

### Policy, phases, and correlation

Current diff/task targets default to `auto`; branch, entire-branch, and PR
targets default to `full`. Explicit tagged `auto`, `full`, or `aspects` values
override the target default, while textual `all` normalizes to `full`. For
`auto`, uncertain triggers are selected; explicit aspects are an allowlist.

Phase A dispatches selected lanes in canonical order through background batches
bounded by the resolved `REVIEWER_MAX_PARALLEL` (1–3; invalid or unset values
resolve to the registry cap of 3). The orchestrator waits for every exact
session in a batch before launching the next. Phase B runs
`reviewer-simplifier` exactly once, fresh and sequentially after Phase A for
executable/source/config content; docs-only full reviews record it as not
applicable. A deadline is terminal; late results are retained as late evidence
but excluded from the verdict.

The immutable packet contains the target, complete relevant diff, changed-path
manifest, diff metadata, implementer report, plan context, guidelines, policy,
contract version, and the correlation envelope (`review_run_id` and
`packet_digest`). Every lane echoes the envelope and returns strict JSON. Every
finding is patch-anchored with a changed file, positive line, changed-side
`side`, and relevant diff `hunk`; findings without a changed location are
omitted.

### Trust and health

Diffs, file contents, task text, comments, commit messages, implementer output,
and tool output are untrusted input. Redact secrets and embedded instructions,
enforce path/packet/output limits, and escape content in child prompts and
Markdown. Native RTK/OpenCode reads are authoritative for exact evidence; do
not infer graph, freshness, timing, or schema semantics.

Review Health is separate from content findings. Missing or inconsistent packet
fields, bad correlation, failed/timed-out/unavailable/malformed/incomplete
lanes, reconciliation or finalization errors, missing native evidence, or
unobserved effective permissions force `Degraded/inconclusive`; health-first
precedence wins over a content verdict. Prompt configuration and parent task
structure do not prove parentage, effective permission isolation, or filesystem
immutability. Static validation is not runtime smoke evidence, and no live
deployment parity is claimed; the known RTK/live-manifest drift remains a
documented limitation.

The shared severity rubric is `Critical`, `Important`, and `Suggestions`.
Actionable findings carry the source lane, changed location, confidence (0–100),
and remediation; health failures are reported separately rather than inflated
into content severity. The deterministic contract tests for registry, packet,
lane-result, and verdict invariants are listed in the reference registry.

---

## 5. Deployment and workspace lifecycle

### Force-only deployment lifecycle

`./deploy.sh` is the only deployment path. Source: [`deploy.sh`](../deploy.sh)
and the [README](../README.md#quick-start).

| Invocation | Effect |
| :--- | :--- |
| `./deploy.sh` | Force-replace the live OpenCode directory from the validated staged payload and resolve latest OMO |
| `./deploy.sh --force` | Equivalent to `./deploy.sh` |
| `./deploy.sh --help` / `-h` | Print usage without deployment |
| unknown flags | Rejected before deployment, including `--check` and `--compatibility-check` |

The staged payload is validated, secret-scanned, and given an ownership
manifest before installation. Full replacement never merges unknown live files.
A durable, ownership/permission-checked transaction marker records `prepared`,
`old_moved`, and `committed` phases while `.opencode.deploy.$$` and
`.opencode.previous.$$` are used for the incoming and displaced trees.
Interrupted transactions are recovered on the next run. Marker and displaced
path cleanup happens only after successful completion; no backup is retained.

RTK is initialized after the replacement and its resulting regular plugin file
is verified in the final live OpenCode directory. Sidecars are installed after
RTK and have no cross-component rollback.

### Code intelligence lifecycle
### Code intelligence lifecycle

Deployment and review use native RTK/OpenCode inspection. No indexed
code-intelligence service or graph-evidence lifecycle is part of the current
configuration. Serena is the active semantic MCP for OpenCode IDE sessions; it
complements native inspection rather than replacing it.
GitNexus is removed and is not an authority or part of the workflow.

Install the pinned Serena version with:

```zsh
uv tool install -p 3.13 serena-agent==1.7.0
```

Serena uses only OpenCode's `ide` context and stdio transport. Its dashboard and
browser are disabled. VS Code integration is deferred. Worktrunk setup creates
and indexes the local Serena project before publishing readiness.

#### Serena and Worktrunk lifecycle

1. Worktrunk creates or enters a worktree.
2. Worktrunk setup runs `serena project create --index`, retrying with
   `serena project index` when needed.
3. OpenCode starts Serena with `--context ide --project-from-cwd`.
4. Serena resolves the nearest `.serena/project.yml` or `.git` boundary.
5. Each client session owns one stdio Serena process.
6. A blocking Worktrunk `pre-remove` hook removes disposable Serena runtime
   state while preserving a tracked `.serena/project.yml`.

Launching from nested `ai-rules` selects its nested Git boundary and does not
inherit the parent `.serena/project.yml`. Nested `ai-rules` Serena
configuration is deferred because Worktrunk worktrees require no changes inside
that nested repository.

### Worktrunk → Orca → OpenCode ownership

Source: [`README.md`](../README.md#worktrunk--orca--opencode-workflow).

- **Worktrunk** is the only Git worktree lifecycle owner (creates/removes
  worktrees). Its setup hook creates/indexes Serena, and its blocking
  `pre-remove` hook cleans disposable Serena runtime state while preserving a
  tracked `.serena/project.yml`.
- **Orca** attaches to an existing Worktrunk path and must not create a second
  checkout.
- **OpenCode** and **oh-my-opencode-slim** run inside the Orca-owned terminal.
  Do not edit generated files under `~/.config/opencode/` directly.

Existing operator commands (from the README; environment-dependent — see note):

```zsh
# Orca recipe path (gorgias-chat/orca.yaml invokes these)
wt-orca start --branch feature/example --name feature-example --base main
wt-orca stop  --name feature-example            # refuses dirty worktrees by default
wt-orca stop  --name feature-example --force    # explicit destructive override

# Manual operation outside an Orca recipe (run from the primary repository)
wt switch --create feature/example
wt-orca attach
wt-orca status
wt-orca detach
wt remove --force                                # explicit Worktrunk-owned removal

# A failed Serena pre-remove hook aborts removal while the worktree still exists;
# fix the reported path/permission issue, then rerun the same removal command.
```

> **Environment-dependent note:** the `wt-orca` / `wt` / `worktree-setup.sh` /
> `worktree-serena.sh` commands are installed by `deploy.sh` from the sibling
> dotfiles directory and are documented here only as referenced in the README.
> Their runtime availability is not re-verified by this documentation pass.

### Validation commands

```bash
# Repository validator (static, from repo root)
python3 scripts/validate-ai-rules.py

# Show deployment usage without mutating anything
./deploy.sh --help
```

---

## 6. Graphs

- [`graphs/dispatch-and-review.mmd`](./graphs/dispatch-and-review.mmd) — sizing
  → implementation → review → escalation flow.
- [`graphs/workspace-lifecycle.mmd`](./graphs/workspace-lifecycle.mmd) —
  Worktrunk → Orca → OpenCode ownership and the force-only deployment and transient transaction-recovery loop.

Reviewed improvement proposals are recorded separately in
[`review-and-improvements.md`](./review-and-improvements.md) (authority
precedence, Detective capability isolation, Claude alignment, model-routing
authority, validator consolidation, provenance). The two graphs here reflect
`Current` behavior, not those proposals.
