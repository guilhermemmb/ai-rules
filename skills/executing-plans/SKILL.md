---
name: executing-plans
description: Use when executing an implementation plan — dispatches fresh agent per task with review after each
---

# Executing Plans

Execute an implementation plan by dispatching a fresh agent per task, reviewing after each, and continuing through all tasks without stopping.

**Why subagents:** You delegate tasks to specialized agents with isolated context. By precisely crafting their instructions and context, you ensure they stay focused. Never let them inherit your session's history — construct exactly what they need.

**Core principle:** Fresh agent per task + review after each = high quality, fast iteration

**Continuous execution:** Do not pause to check in between tasks. Execute all tasks from the plan without stopping. Only stop when: BLOCKED (cannot resolve), ambiguity that genuinely prevents progress, or all tasks complete.

## When to Use

- You have an approved implementation plan from `writing-plans`
- Tasks are mostly independent
- You are staying in the current session

## Agent Dispatch Rules

Assign the right agent per task type:

| Task type | Agent | Model tier |
|---|---|---|
| Code implementation (1-2 files, full spec in plan) | @fixer | xhigh |
| Code implementation (multi-file, integration) | @fixer | xhigh |
| UI/UX implementation (components, styling, layouts) | @designer | medium |
| Architecture decisions, complex debugging | @oracle | high |
| Task review (after each task) | @reviewer | high |
| Escalation (stuck after 2 fix attempts) | @oracle | high |

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

Choose agent: @fixer for code, @designer for UI.

The dispatch prompt includes:
- The exact task text (copy verbatim from the plan)
- Exact file paths, interfaces, and Global Constraints
- A report file path: `docs/.planning/reports/<plan-basename>-task-<N>.md`
- Instruction: "Write your complete status, commit SHAs, test summary, and any concerns to the report file. Return only: status (DONE / NEEDS_CONTEXT / BLOCKED), commits, one-line test summary, concerns."

**2. Handle the report**

| Status | Action |
|---|---|
| DONE | Proceed to review |
| NEEDS_CONTEXT | Provide missing info, re-dispatch |
| BLOCKED | Assess: context problem → provide context and re-dispatch. Task too hard → escalate to @oracle. Plan wrong → report to user. |

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

### Final Review

After all tasks, dispatch @reviewer with the full branch diff for a whole-branch review. If findings exist, do ONE fix wave then one scoped re-review. Adjudicate residuals.

### Finish

Commit the ledger file. Present summary to the user: tasks completed, open items, ready for PR.

## Ledger Format

```
# Execution Ledger — plan: docs/.planning/plans/2026-07-29-feature.md

Task 1: complete (commits a1b2c3d..d4e5f6a, review clean)
Task 2: fix round 1/3 (2 addressed, 0 open — missing validation, magic number; commits d4e5f6a..b7c8d9e)
Task 2: complete (commits d4e5f6a..b7c8d9e, review clean)
Task 3: complete (commits b7c8d9e..e0f1a2b, review clean, 1 parked — cache key naming deferred)
...
Final review: clean
```

The ledger survives context compaction. After compaction, trust the ledger and `git log` over memory.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll fix it myself" | Controller fixes skip review and pollute context. Re-dispatch the implementer. |
| "The fix was small, skip review" | Unreviewed fixes are how regressions land. Every fix gets reviewed. |
| "One more round will converge" | After 3 rounds, the failure is structural. Escalate to @oracle. |
| "I'll just run all tasks myself" | Fresh agents per task = better focus, less context pollution. |
