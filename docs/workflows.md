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
automatically through the OpenCode `reviewer-coordinator`.

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

Intent-to-agent routing. Models are `Current` as declared in
[`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) and the
[`profiles/models/`](../profiles/models/) profiles.

| Intent | Agent | Notes |
| :--- | :--- | :--- |
| Master delegation & coordination | Orchestrator | Default agent; delegates complete review packets to `reviewer-coordinator` |
| Strategic/architecture decisions, escalation | Oracle | Also adjudicates failed review loops |
| Codebase reconnaissance | Explorer | RTK/native discovery |
| External/public research, docs | Librarian | Context7, websearch, Linear, Cortex |
| UI/UX implementation & design | Designer | Native tools + Figma skills; no code-intelligence MCP |
| Scoped code implementation | Fixer | Native tools; hard `Files` allowlist, no architecture decisions |
| Visual analysis | Observer | Auto-routes images from Orchestrator |
| Browser automation | Navigator | `agent-browser` CLI via Bash only |
| Production diagnostics | Detective | `pup`/`gcloud` via Bash, read-only |
| Gorgias domain knowledge | Sage | Cortex MCP, read-only |
| Review coordination (OpenCode) | `reviewer-coordinator` | Receives the orchestrator's complete packet; selects, batches, aggregates, and computes the verdict for 10 read-only lanes |

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

Source:
[`.rulesync/skills/reviewer-coordinator/SKILL.md`](../.rulesync/skills/reviewer-coordinator/SKILL.md)
and the [`review-pr` command](../.rulesync/commands/review-pr.md).

### Coordinator ownership

- **OpenCode:** the orchestrator delegates the complete review packet to
  `reviewer-coordinator`. It does not preload the coordinator skill, select or
  directly dispatch lanes, batch work, aggregate findings, or compute the
  verdict. `reviewer-coordinator` owns exactly ten read-only lanes:
  `reviewer-code`, `reviewer-test`, `reviewer-errors`, `reviewer-types`,
  `reviewer-security`, `reviewer-performance`, `reviewer-data-integrity`,
  `reviewer-accessibility`, `reviewer-comments`, and `reviewer-simplifier`.

### Target-aware policy and result contract

Current diff/task targets default to `auto`; entire branch, branch, and PR
targets default to `full`. Explicit tagged `auto`, `full`, or `aspects` values
override that default. Textual `all` normalizes to `full`. Auto follows the
trigger table; full runs the nine Phase A lanes, then runs
`reviewer-simplifier` exactly once sequentially in Phase B when executable,
source, or config content is present. A docs-only full review does not run the
simplifier.

The coordinator returns one inline Markdown report containing telemetry,
triggered/skipped lanes, batches and exact session IDs, timing, native
RTK/OpenCode evidence, Review Health, verdict, prioritized findings, strengths,
and recommended action.

### Lanes and triggers

Ten specialist lanes; `reviewer-code` always runs unless excluded by an aspect
filter:

| Lane | Trigger |
| :--- | :--- |
| `reviewer-code` | Always — correctness, guidelines, bugs |
| `reviewer-test` | Test files changed, or behavior changed without coverage |
| `reviewer-errors` | Error handling changed |
| `reviewer-types` | Types/interfaces/classes/schemas changed |
| `reviewer-security` | Auth, secrets, validation, permissions changed |
| `reviewer-performance` | Algorithms/loops/queries/caching/hot paths changed |
| `reviewer-data-integrity` | Persistence/migrations/transactions/state changed |
| `reviewer-accessibility` | UI/rendering files changed |
| `reviewer-comments` | Comments/docs/examples changed |
| `reviewer-simplifier` | Any non-empty executable/source/config diff — sequential post-Phase-A pass |

### Phases

- **Phase A** — applicable concern lanes run in batches of at most the resolved
  `REVIEWER_MAX_PARALLEL` limit (integer 1–3; unset/empty/invalid → 3; values
  above 3 clamp to 3). Each lane gets the full diff plus its narrow focus.
- **Phase B** — `reviewer-simplifier` runs **exactly once**, sequentially, after
  all Phase A batches, and receives the consolidated Phase A findings.

### Degraded / inconclusive evidence

Review Health is `Healthy` only when the coordinator identity, resolved
concurrency, completed/failed lane coverage, **and** effective read-only runtime
smoke evidence are all reported. Any of the following forces
`Degraded`/inconclusive:

- any lane `errors` array (failed, timed-out, unavailable, malformed,
  incomplete);
- runtime smoke evidence unavailable, failed, or unable to prove parent
  identity / tool execution;
- effective-permission mismatch (a failed smoke test or permission mismatch).

Review evidence comes from the complete packet and native RTK/OpenCode reads.

Static validation alone is **never** runtime smoke evidence. A
`Degraded`/inconclusive status describes coverage, not a code defect. Runtime
smoke commands live in [`scripts/`](../scripts/) (`smoke-opencode-*-runtime.sh`).

---

## 5. Deployment and workspace lifecycle

### Deployment, check, and rollback

`./deploy.sh` is the source of truth for generated OpenCode configuration.
Source: [`deploy.sh`](../deploy.sh) and the
[README](../README.md#quick-start).

| Command | Effect |
| :--- | :--- |
| `./deploy.sh` | Deploy (refreshes the repository-recorded OMO package when needed) |
| `./deploy.sh --force` | Reinstall the pinned OMO package + deploy |
| `./deploy.sh --check` | Dry-run: validate ownership, report drift, no mutation |
| `./deploy.sh --compatibility-check` | Read-only host/plugin/OMO compatibility evidence |
| `./deploy.sh --model-profile=<name>` | Deploy a named profile (`default` \| `cost-efficient`) |
| `./deploy.sh --help` | Usage |

`deploy.sh` writes `~/.config/opencode/.ai-rules.manifest.json` (owner, version,
timestamp, managed paths, SHA-256s) atomically with the generated config, and
includes it in transaction snapshots and rollback. On failure it restores the
previous configuration and preserves recovery artifacts (see the
`cleanup_stage` / rollback logic in `deploy.sh`).

**RTK initialization** (performed by `deploy.sh` when RTK is missing):

```bash
rtk init -g --opencode --auto-patch
```

The manual prerequisite is `brew install rtk-ai/tap/rtk` (Homebrew only when
RTK is absent). Test with `git status` — RTK rewrites it transparently.

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
browser are disabled. VS Code integration is deferred. Serena has no Worktrunk
hook lifecycle.

#### Serena and Worktrunk lifecycle

1. Worktrunk creates or enters a worktree.
2. OpenCode starts Serena with `--context ide --project-from-cwd`.
3. Serena resolves the nearest `.serena/project.yml` or `.git` boundary.
4. Each client session owns one stdio Serena process.
5. Worktrunk does not start, index, stop, or clean Serena.

Launching from nested `ai-rules` selects its nested Git boundary and does not
inherit the parent `.serena/project.yml`. Nested `ai-rules` Serena
configuration is deferred because Worktrunk worktrees require no changes inside
that nested repository.

### Worktrunk → Orca → OpenCode ownership

Source: [`README.md`](../README.md#worktrunk--orca--opencode-workflow).

- **Worktrunk** is the only Git worktree lifecycle owner (creates/removes
  worktrees). Its `pre-remove` hook owns cleanup and the retry queue. It does
  not start, index, stop, or clean Serena.
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

# Recovery (failed pre-remove cleanup retry)
~/developer/dotfiles/worktree-cleanup.sh --retry-pending --limit 100
```

> **Environment-dependent note:** the `wt-orca` / `wt` / `worktree-setup.sh` /
> `worktree-cleanup.sh` commands are installed by `deploy.sh` from the sibling
> dotfiles directory and are documented here only as referenced in the README.
> Their runtime availability is not re-verified by this documentation pass.

### Validation commands

```bash
# Repository validator (static, from repo root)
python3 scripts/validate-ai-rules.py

# Deployment ownership dry-run
./deploy.sh --check
```

---

## 6. Graphs

- [`graphs/dispatch-and-review.mmd`](./graphs/dispatch-and-review.mmd) — sizing
  → implementation → review → escalation flow.
- [`graphs/workspace-lifecycle.mmd`](./graphs/workspace-lifecycle.mmd) —
  Worktrunk → Orca → OpenCode ownership and the deploy/check/rollback loop.

Reviewed improvement proposals are recorded separately in
[`review-and-improvements.md`](./review-and-improvements.md) (authority
precedence, Detective capability isolation, Claude alignment, profile
authority, validator consolidation, provenance). The two graphs here reflect
`Current` behavior, not those proposals.
