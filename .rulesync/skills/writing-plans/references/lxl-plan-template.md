---
status: pending
approver: null
approval_timestamp: null
approval_evidence: null
---

# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Global Constraints

[The spec's project-wide requirements — version floors, dependency limits,
naming and copy rules, platform requirements — one line each, with exact values
copied verbatim from the spec. Every task's requirements implicitly include
this section.]

---

## File Structure

Map the files created or modified and each responsibility before defining tasks.
Follow established project patterns and keep boundaries explicit.

## Tasks

Each task is the smallest independently testable deliverable that merits a
fresh review gate. Use concrete checkbox steps, exact file paths, interfaces,
constraints, validation commands, and expected results.

### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Interfaces/Constraints:**
- Consumes: [exact inputs, signatures, or earlier task outputs]
- Produces: [exact outputs later tasks rely on]
- Preserves: [global constraints and ordering requirements]

- [ ] **Step 1:** [Concrete action]
- [ ] **Step 2:** [Concrete action]
- [ ] **Step 3:** [Concrete validation action]

Run: `exact validation command`
Expected: `PASS` with the stated acceptance result.

## Handoff Contract

Every dispatched task must include Goal, exact Files, ordered Steps,
Interfaces/Constraints, Validation, and Stop Conditions. Include a Lint Autofix
allowlist only when explicitly desired; otherwise validation is check-only.
Commit steps, if present, are orchestrator-owned and excluded from fixer
dispatch. Tasks with ambiguous write sets, interfaces, or ordering remain
serial. A maximum of three independent tasks may run in one batch.

Before approval, self-review spec coverage, placeholders, interface/type
consistency, and task scope. Persist `status: approved`, approver,
RFC 3339 approval timestamp, and durable approval evidence in this file only
after the orchestrator receives approval. Never execute a pending plan.
