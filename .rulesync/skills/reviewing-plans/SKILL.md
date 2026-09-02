---
name: reviewing-plans
description: Use after executing-plans completes and only after explicit user opt-in — runs the target-specific final comprehensive review before merge
---

# Reviewing Plans

Run a final comprehensive review of all changes produced by the execution phase. Acts as the merge-readiness gate.

**Core principle:** No code merges without passing review. Critical issues block sign-off.

## When to Use

- After `executing-plans` has completed all tasks
- The user has explicitly opted in to run the final comprehensive review
- The execution ledger shows all tasks complete or parked
- You are ready to signal to the user that the plan is done

## Process

### 1. Gather Context

Collect these inputs:
- **Plan file**: the original implementation plan from `writing-plans`
- **Execution ledger**: `~/developer/planning-docs/{{repository-name}}/.planning/ledger-<plan-basename>.md` with all task completions, parked items, and fix-round history
- **Branch diff**: the full diff from merge-base to HEAD

### 2. Run the target-specific review workflow

**OpenCode:** Run the preloaded `reviewer` workflow through the orchestrator.
The orchestrator is the sole coordinator and directly selects and dispatches the
applicable `reviewer-*` lanes. Do not call `functions.skill`, dispatch a nested
`@reviewer` coordinator, or silently fall back to a partial direct-lane review.
Pass it:

- The implementation plan file path
- The execution ledger file path (note parked items and adjudicated findings)
- The full branch diff
- Any Global Constraints from the plan

The orchestrator returns the standard structured review report and owns
selection, bounded execution, failure handling, and aggregation of the ten
`reviewer-*` lanes. Do not dispatch specialist lanes directly or ask them to
dispatch additional tasks.

**Claude Code:** Dispatch `@reviewer` to review the full branch changes. Pass
the same plan, ledger, diff, and Global Constraints context. The Claude
`@reviewer` compatibility coordinator owns selection and bounded execution of
the ten `reviewer-*` lanes; do not dispatch specialist lanes directly.

### 3. Evaluate the Report

The active target coordinator returns the standard report with sections:
- Critical Issues (must fix before sign-off)
- Important Issues (should fix)
- Suggestions (nice to have)
- Strengths (what's well done)
- Recommended Action

The report must also include Review Health. Failed, timed-out, unavailable,
malformed, or incomplete lane results are recorded as lane errors and make
Review Health `Degraded/inconclusive`; valid findings from other lanes remain
in the report, and no finding or citation may be invented for an invalid result.

### 4. The Gate

```
Critical Issues count = 0?
  ├── YES → Plan executed successfully.
  │       Report findings to orchestrator.
  │       Include: tasks completed, review summary, parked items,
  │       strengths, recommended action for the user (merge/PR/polish).
  │
  └── NO  → Review gate NOT passed.
          Report findings to orchestrator.
          Include: all Critical issues with file:line references,
          recommendation to fix before merge.
          Do NOT signal plan completion.
```

**The success signal is**: "Plan executed with success — review passed with 0 Critical issues."

If Critical issues exist, the reviewing-plans step reports them and does NOT declare success. The orchestrator decides whether to fix and re-review or escalate.

## Output Format

Return a concise summary to the orchestrator:

```
# Review Gate Report

**Plan:** <plan file>
**Review passed:** <YES / NO>
**Critical issues:** <N>

## Critical Issues (if any)
- [reviewer-X] file:line — description

## Important Issues
- [reviewer-X] file:line — description

## Parked Items (from ledger)
- Task N: parked — finding — ruling

## Strengths
- What the implementation did well

## Recommended Action
- [If passed]: Ready for merge. Consider Important items at your discretion.
- [If not passed]: Fix Critical items above, then re-run reviewing-plans.
```

## Rules

- **Explicit user opt-in is required**: Do not load this skill or start the final comprehensive review unless the user explicitly chooses to run it. On OpenCode, the orchestrator runs the preloaded workflow directly; on Claude Code, the compatibility path dispatches `@reviewer`.
- **No code changes**: Reviewing-plans is advisory only. Never fix issues inline.
- **Binary gate**: Critical = 0 → success. Any Critical > 0 → not passed.
- **Trust the ledger**: Parked items with rulings from executing-plans are resolved. Do not re-litigate.
- **Report, don't decide**: Present findings to the orchestrator. Let the orchestrator decide next steps.
