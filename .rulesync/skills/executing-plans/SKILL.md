---
name: executing-plans
description: Use only for approved L/XL SDD implementation plans — dispatches fresh agent per task with review after each
---

# Executing Plans

Use this only after the orchestrator has shown the scale
`T-shirt size: XS | S | M | L | XL`, selected L/XL with a rationale, and
received the required plan approval.

Execute an approved L/XL SDD implementation plan by dispatching a fresh agent
per task, reviewing after each, and continuing through all tasks without
stopping.

**Why subagents:** You delegate tasks to specialized agents with isolated context. By precisely crafting their instructions and context, you ensure they stay focused. Never let them inherit your session's history — construct exactly what they need.

**Core principle:** Fresh agent per task + review after each = high quality, fast iteration

**Continuous execution:** Do not pause to check in between tasks. Execute all tasks from the plan without stopping. Only stop when: BLOCKED (cannot resolve), ambiguity that genuinely prevents progress, or all tasks complete.

## When to Use

- The work is classified as L or XL and has an approved SDD implementation plan
  from `writing-plans`
- Tasks are mostly independent
- You are staying in the current session

Do not use this skill for XS, S, or M work, or for explicitly direct-execution
work. S/M combined plans are executed directly after one approval with
proportionate validation; they are not converted into execution plans.

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
2. Create a ledger file at `docs/.planning/ledger-<plan-basename>.md`:
   ```
   # Execution Ledger — plan: <plan file path>
   ```
3. Create a todo per task from the plan.
4. Scan for pre-flight conflicts: tasks that contradict each other or the plan's Global Constraints. Batched to the user before execution.

### Per-Task Loop

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
- A report file path: `docs/.planning/reports/<plan-basename>-task-<N>.md`

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

After clean review — or @oracle adjudication — append to ledger:
```
Task <N>: complete (commits <base>..<head>, review clean)
```
Check the todo and continue.

### Handoff to Review

After all tasks complete, commit the ledger file and ask the user whether to run the final comprehensive review. This is a mandatory user-choice gate. Do not load skill `reviewing-plans` or dispatch @reviewer unless the user explicitly chooses to run the review.

- If the user opts in, load skill `reviewing-plans`. It will dispatch @reviewer with the plan file, ledger, and full branch diff, then present the structured report to the user.
- If the user skips it, append `Handoff: final review skipped by user` to the ledger and state that the merge-readiness review was not run.

## Ledger Format

```
# Execution Ledger — plan: docs/.planning/plans/2026-07-29-feature.md

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
