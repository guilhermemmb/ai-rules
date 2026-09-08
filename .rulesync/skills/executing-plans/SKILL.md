---
name: executing-plans
description: Use only for approved L/XL SDD implementation plans — dispatches fresh agent per task with dependency-aware batching and review after each
---

# Executing Plans

Use this only for an orchestrator-selected, approved L/XL implementation plan.
Follow `.rulesync/rules/planning-state.md` for canonical paths, approval gates,
ledger authority, and resume behavior. XS and S/M use their own workflows.

The scheduler runs a fresh fixer per task, batches only proven-independent work,
reviews every completed task, reconciles state, and continues until completion
or a genuine blocker.

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
3. Send every `DONE` task to exactly one orchestrator-managed
   `review-pipeline`, preserving the existing per-task review boundary.
4. Reconcile reports, review verdicts, and changed paths against each task's
   hard `Files` allowlist. A task is releasable only after a passing review or
   explicit @oracle adjudication. Append validation evidence and task state to
   the ledger.
5. Release dependent tasks only after all required predecessors are releasable;
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

If a review requests changes, allow at most three fix rounds: re-dispatch the
same implementer for rounds 1–2, a fresh fixer for round 3, then escalate to
@oracle if still unresolved. Re-review every fix.

## Final handoff

After all tasks are complete, commit the ledger file and ask the user whether to
run the final comprehensive review. This is a mandatory user-choice gate. Do
not load `reviewing-plans` or `review-pipeline` unless the user explicitly
chooses to run the review.

- If the user opts in, load `reviewing-plans`; the orchestrator then loads
  `review-pipeline` at the boundary with the plan, ledger, full branch diff,
  target descriptor, review mode, and Global Constraints.
- If the user skips it, append `Handoff: final review skipped by user` to the
  ledger and state that the merge-readiness review was not run.

## Ledger format

```text
# Execution Ledger — plan: canonical planning `plans/2026-07-29-feature.md`

Task 1: complete (commits a1b2c3d..d4e5f6a, review clean)
Task 2: fix round 1/3 (2 addressed, 0 open, review pending)
Task 2: complete (commits d4e5f6a..b7c8d9e, review clean)
Task 3: queued (blocked by Task 2)
Handoff: final review skipped by user
```

The ledger survives context compaction. On resume, trust the approved plan,
ledger, reports, and git evidence over conversation memory.
