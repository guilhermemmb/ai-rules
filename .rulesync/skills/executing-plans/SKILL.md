---
name: executing-plans
description: Use only for approved L/XL SDD implementation plans — dispatches fresh agents with dependency-aware batching, one review report per completed batch, and mandatory final review
---

# Executing Plans

Use this only for an orchestrator-selected, approved L/XL implementation plan.
Follow `.rulesync/rules/planning-state.md` for canonical paths, approval gates,
ledger authority, and resume behavior. XS and S/M use their own workflows.

The scheduler runs a fresh fixer per task, batches only proven-independent work,
produces one combined review report after each completed fixer batch, reconciles
state, and continues until completion or a genuine blocker.

Before any transition or dispatch, verify the plan exists and its persisted
metadata says `status: approved` with non-null approver, approval timestamp, and
approval evidence. An L/XL plan also requires its source spec to be approved.
Pending or malformed metadata blocks execution and is surfaced to the user.

## Scheduler lifecycle

### 1. Setup

1. Read the approved plan once and note its Global Constraints.
2. Create or resume the authoritative ledger at the canonical planning root as
   `ledger-<plan-basename>.md`:

   ```text
   # Execution Ledger — plan: <plan file path>
   ```

3. Create a todo per task and record the current task states.
4. Scan for pre-flight conflicts. Do not dispatch conflicting or ambiguous
   tasks; surface them before execution.

### 2. Classify and batch

Classify pending tasks conservatively from their declared `Files` and
`Interfaces/Constraints`:

1. Overlapping, missing, incomplete, or unclear write sets serialize.
2. A producer/consumer interface dependency runs the producer first.
3. Explicit ordering, migrations, shared resources, and data-integrity work
   serialize even when files are disjoint.
4. Only tasks with complete disjoint write sets and no interface, shared-state,
   or ordering dependency may share a batch.

The scheduler may dispatch at most **3** concurrent `@fixer` children with
`background=true`. Every created, modified, deleted, generated, lockfile,
report, and planning-artifact path belongs to a task write set. Unowned,
shared, generated, or ambiguous paths serialize.

### 3. Dispatch, review, and reconcile

`.rulesync/skills/fixer/SKILL.md` is authoritative for validation commands,
start/terminal events, and report schema. Preserve each fixer's ordered events
verbatim in the task report and ledger; never reduce them to a boolean or
convert a non-passed outcome into passed.

For each ready batch:

1. Select only tasks whose predecessors are releasable. Dispatch one fresh
   `@fixer` per task with non-overlapping ownership and the full task handoff.
2. Wait for every report in the batch. Reconcile each result using its exact
   returned session ID and job ID, not an alias or ordering assumption.
3. After every task in the batch is reconciled, send one combined packet for
   the completed fixer batch to exactly one orchestrator-managed
   `review-pipeline`, producing one consolidated Markdown report for the batch.
4. Reconcile the batch report, its health status, and changed paths against
   every task's hard `Files` allowlist. A degraded or inconclusive report holds
   release or requires explicit @oracle adjudication. Findings are report-only:
   the user chooses whether to fix, defer, or accept them; never auto-fix,
   auto-accept, or require acceptance metadata. Append validation evidence,
   batch-review evidence, and task state to the ledger.
5. Release dependent tasks only after the completed batch report is reconciled;
   unrelated ready tasks may continue.

### Dispatch contract

The dispatch payload includes, verbatim:

- `Goal` — one sentence describing the task.
- `Files` — exact paths with Create/Modify/Test annotations.
- `Steps` — ordered checkbox steps from the plan, excluding commit steps.
- `Interfaces/Constraints` — consumed, produced, and preserved interfaces.
- `Validation` — exact commands and expected results.
- `Lint Autofix` — only when explicitly permitted, with a file allowlist.
- `Stop Conditions` — conditions requiring escalation.
- Global Constraints and selected model tier.
- Canonical report path:
  `reports/<plan-basename>-task-<N>.md`.

Dispatch code tasks to `@fixer` and UI tasks to `@designer`; use the model tier
specified by the plan. Tell every implementer not to commit or push. If a task
is ambiguous, exceeds its `Files` allowlist, or combines unrelated concerns,
hold it for refinement or escalation rather than guessing.

If the user selects remediation from a batch report, allow at most three fix
rounds for the selected task(s): re-dispatch the same implementer for rounds 1–2,
a fresh fixer for round 3, then escalate to @oracle if still unresolved. Reconcile
the resulting batch and produce one combined re-review report. Never auto-fix or
auto-accept findings from a report.

## Final handoff

After all tasks and batch reports are complete, load `reviewing-plans` and run one
mandatory final comprehensive branch review. The orchestrator loads
`review-pipeline` at the boundary with the plan, ledger, full branch diff, target
descriptor, review mode, and Global Constraints. Retain the final Markdown report
and reconcile its health before final handoff or commit authorization. The final
review cannot be skipped.

Final findings are report-only: the user selects what to fix, defer, or accept.
Do not auto-fix, auto-accept, or require acceptance metadata. Git commits remain
user-authorized and still require the existing security scan.

## Ledger format

```text
# Execution Ledger — plan: canonical planning `plans/2026-07-29-feature.md`

Batch 1: complete (tasks 1–2 reconciled; combined review report recorded)
Task 1: complete (implementer report recorded)
Task 2: complete (implementer report recorded)
Batch 2: queued (blocked by Batch 1 health)
Final review: mandatory branch report recorded (findings report-only)
Handoff: awaiting user remediation decisions and commit authorization
```

The ledger survives context compaction. On resume, trust the approved plan,
ledger, reports, and git evidence over conversation memory.
