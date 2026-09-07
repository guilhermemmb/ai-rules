---
name: writing-plans
description: Use for approved L/XL specs or classified S/M work before touching code
---

# Writing Plans

Use this only after the orchestrator has shown the scale
`T-shirt size: XS | S | M | L | XL`, the selected size, and its rationale.

## Overview

Write the plan format appropriate to the T-shirt size. For L/XL work, write a
comprehensive implementation plan assuming the engineer has zero context for
our codebase and questionable taste. For S/M work, write one concise merged SDD
+ implementation plan. DRY. YAGNI. TDD where proportionate.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save plans to:** `~/developer/planning-docs/{{repository-name}}/.planning/plans/YYYY-MM-DD-<feature-name>.md`

## Scope Check

For L/XL specs, if the work covers multiple independent subsystems, it should
have been broken into sub-project specs during brainstorming. If it wasn't,
suggest breaking this into separate plans — one per subsystem. Each full plan
should produce working, testable software on its own. S/M work remains one
cohesive outcome.

## Mode Selection

- **S/M:** use the combined-plan format below. Do not require a
  separate spec or split the outcome into independently reviewed tasks; after
  implementation, load the on-demand `review-pipeline` skill at the review
  boundary and run one automatic post-implementation review owned by the
  orchestrator.
- **L/XL:** use the full SDD implementation-plan format below after
  the separate spec has been approved.

## File Structure

For L/XL SDD plans, before defining tasks, map out which files will be created
or modified and what each one is responsible for. This is where decomposition
decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure — but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.

This structure informs L/XL task decomposition. Each task should produce
self-contained changes that make sense independently.

## S/M Combined SDD + Implementation-Plan Format

Use this format only for S/M work. S is small local work using established
patterns and straightforward validation. M is one cohesive bounded outcome
across a small set of related files, with no architecture, security, migration,
data-integrity, or external-integration uncertainty. Save exactly one document
to `~/developer/planning-docs/{{repository-name}}/.planning/plans/YYYY-MM-DD-<topic>.md`:

````markdown
# [Outcome] S/M Combined SDD + Implementation Plan

> **T-shirt size:** S or M — one approval, specialist implementation, and one automatic post-implementation review

## Design Rationale

[Why this approach is appropriate and which established pattern it follows]

## Scope and Files

- Modify: `exact/path/to/file`
- [Other related files, if needed]
- Out of scope: [Explicit boundaries]

## Implementation Steps

1. [Concrete step with the relevant behavior or content]
2. [Concrete step with the relevant behavior or content]

## Validation

- [Proportionate test, lint, or manual check]
- [Expected result]
````

Keep the document concise and unified: it merges rationale, scope/files,
implementation steps, and validation rather than reproducing a separate spec.

### Combined-Plan Handoff

Present the completed document once and ask for one approval. After approval,
dispatch implementation to `@fixer` for code or `@designer` for UI/UX as
appropriate, then load `review-pipeline` at the review boundary and run exactly
one post-implementation review owned by the orchestrator. Do **not** load
`executing-plans`, create a ledger, dispatch a per-task review loop, or ask for
a review choice.

## L/XL Full SDD Implementation-Plan Format

Use the following format only for L/XL work after the separate design/spec has
been approved.

## Task Right-Sizing

A task is the smallest unit that carries its own test cycle and is worth a fresh reviewer's gate. When drawing task boundaries: fold setup, configuration, scaffolding, and documentation steps into the task whose deliverable needs them; split only where a reviewer could meaningfully reject one task while approving its neighbor. Each task ends with an independently testable deliverable.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code to make the test pass" — step
- "Run the tests and make sure they pass" — step
- "Commit" — step

## L/XL SDD Plan Document Header

**Every L/XL SDD plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Global Constraints

[The spec's project-wide requirements — version floors, dependency limits,
naming and copy rules, platform requirements — one line each, with exact
values copied verbatim from the spec. Every task's requirements implicitly
include this section.]

---
```

## L/XL SDD Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Interfaces:**
- Consumes: [what this task uses from earlier tasks — exact signatures]
- Produces: [what later tasks rely on — exact function names, parameter
  and return types. A task's implementer sees only their own task; this
  block is how they learn the names and types neighboring tasks use.]

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit (orchestrator-owned; exclude from fixer dispatch)**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## No Placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may be reading tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Fixer Task Handoff Contract

Every implementation task dispatched to @fixer must include these fields in the task structure. Missing fields prevent dispatch — resolve them during planning:

| Field | Required | Content |
|---|---|---|
| Goal | Yes | One sentence describing what this task builds |
| Files | Yes | Exact paths with Create/Modify/Test annotations |
| Steps | Yes | Ordered checkbox steps with concrete code blocks |
| Interfaces/Constraints | Yes | What this task consumes, produces, and must preserve |
| Validation | Yes | Commands to run and expected results |
| Lint Autofix | If omitted | List of files where autofix is permitted. Omit to default to check-only. |
| Stop Conditions | If omitted | Conditions that require escalation instead of continuation |

Tasks without explicit file paths, acceptance criteria, or validation commands must be refined before dispatch. Unresolved cross-boundary or architecture decisions must be surfaced in `Interfaces/Constraints` — fixers do not make design calls.

For implementation scheduling, each task must also declare its complete write
set and dependency metadata in `Files` and `Interfaces/Constraints`: producers,
consumers, shared resources, generated outputs, lockfiles, and explicit ordering.
Every path the fixer may create, modify, delete, or generate belongs in the
hard `Files` allowlist; reports and planning artifacts are not implicit outputs.
Only ready tasks with pairwise disjoint, complete write sets and no interface,
shared-state, or ordering dependency may share an OpenCode batch. The
orchestrator may dispatch at most **3** independent `@fixer` children with
`background=true`, waits for the same batch, reconciles exact returned session
IDs with `task_result`, and requires a per-child review before releasing a
dependent. Missing or ambiguous metadata stays serial.

**Commit steps:** Plans may include `- [ ] Commit` steps with `git commit` commands. These steps MUST be excluded when dispatching to @fixer. Commits are orchestrator-owned: the fixer implements code and reports status, but does not stage or commit. If the plan's task text contains a commit step, the dispatch payload must explicitly exclude it or append `Commits are orchestrator-owned — do not commit.` to the `Steps` field.

### Task-Size Guidance by Model Tier

**Pro (xhigh)** — may receive bounded multi-file changes when every file and acceptance criterion is named in the plan. Cohesive outcome across explicitly listed files; still a single concept.

**Flash (cost-efficient)** — single-file or single-concept work. Complex refactors, integration changes, and multi-area work must be split into separate tasks before dispatch. A Flash task that touches 4+ unrelated files or combines concepts is a planning bug.

Split unrelated areas at plan time — do not rely on the fixer to discover the split. When in doubt, prefer smaller Flash tasks over fewer Pro tasks.

## L/XL SDD Self-Review

After writing the complete plan, review it with fresh eyes:

1. **Spec coverage:** Skim each section/requirement in the spec. Point to a task that implements it? List any gaps.
2. **Placeholder scan:** Search your plan for any of the patterns from the "No Placeholders" section above. Fix them.
3. **Type consistency:** Do the types, method signatures, and property names in later tasks match what you defined in earlier tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

If you find issues, fix them inline. No need to re-review — just fix and move on. If you find a spec requirement with no task, add the task.

## L/XL Execution Handoff

After saving an L/XL SDD plan, tell the user:

**"Plan complete and saved to `~/developer/planning-docs/{{repository-name}}/.planning/plans/<filename>.md`. Ready to execute — I'll dispatch a fresh subagent per task with review after each. Shall I proceed?"**

**If user says yes:**
- Load skill `executing-plans`
- Fresh @fixer per implementation task, @designer for UI tasks
- load `review-pipeline` at each review boundary; the orchestrator owns the
  review-pipeline after each task (spec compliance + code quality)
- @oracle for architecture escalations
- Continuous execution — no checkpoints unless BLOCKED
