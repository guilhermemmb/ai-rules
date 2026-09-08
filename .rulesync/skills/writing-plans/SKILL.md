---
name: writing-plans
description: Use for approved L/XL specs or classified S/M work before touching code
---

# Writing Plans

Use this only after the orchestrator has selected the S/M combined-plan or L/XL
full-plan mode and supplied the required approval context. Follow
`.rulesync/rules/planning-state.md` for approval metadata, ownership, paths, and
state transitions; do not reclassify the work or duplicate that contract.

## Overview

Use the orchestrator-selected mode and its referenced template. Keep the plan
concrete, scoped, and proportionate; do not invent a different mode.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save plans to:** the canonical `plans/` directory defined in
`.rulesync/rules/planning-state.md`.

## Scope Check

Validate the selected work without changing its classification: L/XL must be
decomposed into independently testable tasks, and S/M must remain one cohesive
outcome. If the scope is incompatible, report the boundary to the orchestrator
rather than reclassifying it.

## Templates

- S/M combined plan: [references/sm-plan-template.md](references/sm-plan-template.md)
- L/XL implementation plan: [references/lxl-plan-template.md](references/lxl-plan-template.md)

Use exactly one template. Save the resulting plan to the canonical `plans/`
directory. Start it as `status: pending` with the required approval fields.
After the single S/M approval or L/XL plan approval, persist `status: approved`,
approver, RFC 3339 approval timestamp, and durable approval evidence in that
same file. Never hand off or dispatch from a pending plan.

### Combined-plan Handoff

Present the completed S/M document once and ask for one approval. After
approval is persisted, dispatch implementation to `@fixer` for code or
`@designer` for UI/UX as appropriate, then load `review-pipeline` at the review
boundary and run exactly one post-implementation review owned by the
orchestrator. Do not load `executing-plans`, create a ledger, dispatch a
per-task review loop, or ask for a review choice.

## Fixer Task Handoff Contract

Every L/XL implementation task dispatched to `@fixer` must include these fields:

| Field | Required | Content |
|---|---|---|
| Goal | Yes | One sentence describing what this task builds |
| Files | Yes | Exact paths with Create/Modify/Test annotations |
| Steps | Yes | Ordered checkbox steps with concrete code or content |
| Interfaces/Constraints | Yes | What the task consumes, produces, and must preserve |
| Validation | Yes | Commands and expected results |
| Lint Autofix | If omitted | Check-only; list files only when autofix is explicitly desired |
| Stop Conditions | If omitted | Conditions requiring escalation |

Every task must declare its complete write set and dependency metadata,
including generated outputs, lockfiles, reports, and planning artifacts. Only
tasks with disjoint complete write sets and no interface, shared-state, or
ordering dependency may share a batch. The scheduler may dispatch at most
three independent fixer children. Ambiguous metadata stays serial.

Commit steps are orchestrator-owned and must be excluded from fixer dispatch;
append `Commits are orchestrator-owned — do not commit.` when needed.

## L/XL Handoff

Before approval, self-review spec coverage, placeholders, interface/type
consistency, task scope, and validation. Do not hand off until the L/XL source
spec and plan both have approved persisted metadata.

After saving an approved L/XL plan, tell the user:

**"Plan complete and saved under the canonical `plans/` directory. Ready to execute — I'll dispatch a fresh subagent per task with review after each. Shall I proceed?"**

If the user says yes, load `executing-plans`: use a fresh `@fixer` per task,
`@designer` for UI tasks, `review-pipeline` at each review boundary, and
`@oracle` for architecture escalations. Continue without checkpoints unless
blocked.
