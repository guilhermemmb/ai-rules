---
name: executing-plans
description: Use only for approved L/XL SDD implementation plans — dispatches fresh agent per task with dependency-aware batching and review after each
---

# Executing Plans

Use this only after the orchestrator has shown the scale
`T-shirt size: XS | S | M | L | XL`, selected L/XL with a rationale, and
received the required plan approval.

Execute an approved L/XL SDD implementation plan by dispatching a fresh agent
per task, batching only proven-independent tasks, reviewing every completed
task, and continuing through all tasks without stopping.

**Why subagents:** You delegate tasks to specialized agents with isolated context. By precisely crafting their instructions and context, you ensure they stay focused. Never let them inherit your session's history — construct exactly what they need.

**Core principle:** Fresh agent per task + review for every completed task = high quality, fast iteration

**Continuous execution:** Do not pause to check in between tasks. Execute all tasks from the plan without stopping. Only stop when: BLOCKED (cannot resolve), ambiguity that genuinely prevents progress, or all tasks complete.

## When to Use

- The work is classified as L or XL and has an approved SDD implementation plan
  from `writing-plans`
- Tasks have enough declared metadata for conservative dependency classification;
  independent tasks may batch, while dependent or ambiguous tasks serialize
- You are staying in the current session

Do not use this skill for XS, S, or M work. S/M combined plans follow their own
workflow: after one approval, dispatch implementation to `@fixer` for code or
`@designer` for UI/UX as appropriate, then automatically dispatch one
post-implementation `@reviewer` and run proportionate validation. S/M does not
use this skill, its ledger, or its per-task review loop, and does not ask for a
review choice; the reviewer is required through the combined-plan workflow.

## Agent Dispatch Rules

Assign the right agent per task type:

| Task type | Agent | Model tier |
|---|---|---|
| Code implementation (1-2 files, full spec in plan) | @fixer | xhigh |
| Code implementation (multi-file, integration) | @fixer | xhigh |
| UI/UX implementation (components, styling, layouts) | @designer | medium |
| Architecture decisions, complex debugging | @oracle | high |
| Task review (after each task) | @reviewer | high |
| Escalation (stuck after 3 fix rounds) | @oracle | high |

## The Process

### Setup

1. Read the plan file once. Note its Global Constraints.
2. Create a ledger file at `~/developer/planning-docs/{{repository-name}}/.planning/ledger-<plan-basename>.md`:
   ```
   # Execution Ledger — plan: <plan file path>
   ```
3. Create a todo per task from the plan.
4. Scan for pre-flight conflicts: tasks that contradict each other or the plan's Global Constraints. Batched to the user before execution.

### Dependency Classification and Batch Lifecycle

Before dispatching any task, classify pending tasks from the plan's declared
`Files` and `Interfaces/Constraints`. Be conservative: do not infer
independence from names, presumed implementation details, or conversational
context.

1. **Write-set check:** Treat every path a task may create, modify, delete, or
   generate as its write set. If two tasks have overlapping write sets, they
   serialize. A missing, incomplete, or unclear `Files` declaration is
   ambiguous and stays serial.
2. **Interface check:** Treat named artifacts, symbols, files, APIs, schemas,
   migrations, and other outputs in `Interfaces/Constraints` as produced or
   consumed interfaces. If one task consumes an interface produced or changed
   by another, the producer runs first and the consumer waits. If the
   producer/consumer relationship or output identity is ambiguous, serialize
   rather than guess.
3. **Shared-state and ordering check:** Explicit task ordering, migrations,
   shared resources, data-integrity work, or any plan-declared sequencing is a
   dependency even when file sets are disjoint. These tasks serialize.
4. **Batch eligibility:** Only tasks with disjoint, complete write sets and no
   declared or inferred interface, shared-state, or ordering dependency may be
   placed in the same batch. A task with missing or ambiguous metadata is not
   eligible for batching.

Run the following lifecycle for each batch:

1. Select only ready tasks whose required predecessor tasks have completed
   implementation and passed review. Dispatch one fresh specialist per ready
   task in the batch, with explicit non-overlapping ownership.
2. Wait for an implementer report from every dispatched task in the batch
   before advancing that batch. Track each task/session ID; do not release a
   dependent task based on a partial report.
3. Send every `DONE` task to review, respecting the available reviewer cap.
   Queue excess reviews until a reviewer slot is available. Parallel reviewer
   dispatch is limited to this bounded batch review and is not permission for
   arbitrary conversational tool-call parallelism.
4. Reconcile all implementer reports and reviews. A task is releasable only
   after a passing review, or an explicit @oracle adjudication that resolves
   the review under the existing escalation rules. Append each completed task
   to the ledger.
5. Start a dependent batch only after every required predecessor is releasable.
   Unrelated ready tasks may continue through their own batches while a
   predecessor is blocked or being fixed; dependent tasks remain queued.

If an overlap or dependency is discovered after dispatch, stop the affected
lanes from making further conflicting writes, preserve completed unrelated
work, and escalate the ownership conflict for re-sequencing. Never guess which
lane owns a shared file or output. A `NEEDS_CONTEXT` or `BLOCKED` task holds
its dependents; unrelated tasks may finish. Apply the existing re-dispatch,
fix-round, and @oracle escalation rules before releasing dependents.

### Per-Task Loop

The loop below runs for each task within the dependency-aware batch lifecycle;
it does not authorize dispatching tasks that have not been classified as
independent and ready.

**1. Dispatch the implementer**

Choose agent: @fixer for code, @designer for UI. Select the model tier from the agent dispatch rules table above.

The dispatch payload includes, verbatim:
- `Goal` — one-sentence task objective
- `Files` — exact file paths with create/modify/test annotations
- `Steps` — ordered checkbox steps from the plan (exclude any commit steps; see below)
- `Interfaces/Constraints` — what the task consumes, produces, and must preserve
- `Validation` — exact commands and expected results
- `Lint Autofix` — (optional) if lint autofix is desired, list permitted files. Omit to default to check-only.
- `Stop Conditions` — conditions requiring early escalation (if present in plan)
- Global Constraints — copied from the plan header
- Selected model tier — Pro (xhigh) or Flash (cost-efficient)
- A report file path: `~/developer/planning-docs/{{repository-name}}/.planning/reports/<plan-basename>-task-<N>.md`

Also instruct the agent not to run `git commit` or `git push` autonomously.

**Commit steps in plan tasks:** If the plan includes `- [ ] Commit` steps, exclude them from the dispatched `Steps` and append: `Commits are orchestrator-owned — do not commit.` The fixer implements and reports; only the orchestrator stages and commits after review.

**Pre-dispatch scope check:** If a task combines unrelated concerns, spans files not in the `Files` list, or has missing acceptance criteria, split or refine it before dispatch. Do not hand ambiguous tasks to the implementer.

**2. Handle the report**

The implementer returns a structured status report:

```
<status>DONE|NEEDS_CONTEXT|BLOCKED</status>
<summary>Brief summary</summary>
<changes>- file1.ts: Changed X to Y</changes>
<verification>
- Tests passed: [yes/no/skip reason]
- Lint: [passed/failed/autofixed — list files if autofixed]
- Validation: [passed/failed/skip reason]
</verification>
<concerns>- [any concerns or "none"]</concerns>
```

| Status | Action |
|---|---|
| DONE | All steps completed with passing validation — proceed to review |
| NEEDS_CONTEXT | Handoff missing required fields or ambiguous acceptance criteria — provide missing info, re-dispatch. Do not adjust the task scope; the plan is authoritative. |
| BLOCKED | Plan or environment prevents completion (stale paths, missing dependencies, incompatible constraints). Assess: fixable context gap → provide context and re-dispatch. Task exceeds fixer bounds → escalate to @oracle. Plan wrong → report to user. |

**3. Review the task**

Dispatch @reviewer with:
- The task brief file path
- The implementer's report file path
- The diff (git log --oneline + git diff from task start to HEAD)
- Global Constraints

The reviewer returns: spec compliance (✅/❌), task quality (approved/needs work), issues by severity.

**4. Fix loop (if review ❌)**

Max 3 fix rounds per task:

- Rounds 1-2: re-dispatch to the same implementer with findings
- Round 3: dispatch fresh @fixer/@designer with findings + "A prior implementer attempted this. Read the report for what was tried."
- After round 3: if still failing, escalate to @oracle: "This task has failed 3 fix rounds. Review findings and determine if the plan needs adjustment or if this can be deferred."

**5. Complete the task**

After clean review — or an explicit @oracle adjudication that resolves the
review — append to ledger:
```
Task <N>: complete (commits <base>..<head>, review clean)
```
Check the todo and continue only with the current batch's remaining tasks or a
newly eligible batch. Do not start a dependent batch until its required
predecessors are complete and releasable.

### Handoff to Review

After all tasks complete, commit the ledger file and ask the user whether to run the final comprehensive review. This is a mandatory user-choice gate. Do not load skill `reviewing-plans` or dispatch @reviewer unless the user explicitly chooses to run the review.

- If the user opts in, load skill `reviewing-plans`. It will dispatch @reviewer with the plan file, ledger, and full branch diff, then present the structured report to the user.
- If the user skips it, append `Handoff: final review skipped by user` to the ledger and state that the merge-readiness review was not run.

## Ledger Format

```
# Execution Ledger — plan: ~/developer/planning-docs/{{repository-name}}/.planning/plans/2026-07-29-feature.md

Task 1: complete (commits a1b2c3d..d4e5f6a, review clean)
Task 2: fix round 1/3 (2 addressed, 0 open — missing validation, magic number; commits d4e5f6a..b7c8d9e)
Task 2: complete (commits d4e5f6a..b7c8d9e, review clean)
Task 3: complete (commits b7c8d9e..e0f1a2b, review clean, 1 parked — cache key naming deferred)
...
Handoff: reviewing-plans dispatched after user opt-in
# Or, when the user skips the optional final review:
Handoff: final review skipped by user
```

The ledger survives context compaction. After compaction, trust the ledger and `git log` over memory.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll fix it myself" | Controller fixes skip review and pollute context. Re-dispatch the implementer. |
| "The fix was small, skip review" | Unreviewed fixes are how regressions land. Every fix gets reviewed. |
| "One more round will converge" | After 3 rounds, the failure is structural. Escalate to @oracle. |
| "I'll just run all tasks myself" | Fresh agents per task = better focus, less context pollution. |
