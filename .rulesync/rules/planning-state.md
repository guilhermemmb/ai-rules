---
description: Canonical planning and execution state contract
---
# Planning State

This is the single contract for planning and execution state. The orchestrator
selects the T-shirt size and workflow mode before invoking a planning skill;
skills consume that choice and never reclassify the work.

## Canonical storage

The planning root is:

```text
~/developer/planning-docs/{{repository-name}}/.planning/
```

Use only these canonical locations:

- `specs/` — L/XL design/spec documents from brainstorming.
- `plans/` — S/M combined plans or L/XL implementation plans from
  writing-plans.
- `reports/` — per-task implementation reports from executing-plans.
- `ledger-<plan-basename>.md` — the L/XL execution ledger at the planning root.

## Persisted approval metadata

Every spec and plan is a durable Markdown artifact with a frontmatter approval
record. The record must contain exactly these fields (use `null` while pending):

```yaml
status: pending | approved
approver: null | <person or orchestrator identity>
approval_timestamp: null | <RFC 3339 timestamp>
approval_evidence: null | <durable message, decision, or artifact reference>
```

An `approved` artifact must have a non-null approver, timestamp, and evidence.
A `pending` artifact must not be used to pass a gate. The metadata is part of
the artifact, not conversation-only state.

- An L/XL spec in `specs/` is created as `pending` and becomes `approved` only
  after the user approves the design/spec.
- An L/XL plan in `plans/` is created as `pending` and becomes `approved` only
  after the orchestrator receives plan approval. Its spec must also be
  approved.
- An S/M combined plan in `plans/` is created as `pending` and becomes
  `approved` after its single approval. It has no separate spec.

## Ownership and state transitions

- **Orchestrator:** selects size and mode, owns persisted approvals, scheduling,
  dependency classification, review boundaries, and final handoff.
- **Brainstorming:** L/XL only; refines the request and writes the separate
  spec in `specs/`.
- **Writing-plans:** consumes the selected mode and required approved inputs,
  then writes one plan in `plans/`.
- **Executing-plans:** consumes only an approved L/XL plan, dispatches work,
  records reports and ledger state, produces one combined review report per
  completed fixer batch, produces the mandatory final review report, and hands
  off.
- **Fixer/designer:** implement dispatched tasks and report validation; they do
  not choose workflow mode or commit/push autonomously.

S/M is one approved combined-plan flow: no separate spec, execution ledger, or
per-task execution loop. L/XL is the gated flow
`approved spec -> approved plan -> ledger-backed execution -> batch review reports -> mandatory final review report -> handoff`.
XS executes immediately and does not enter these artifacts.

## Resume and gate rules

On resume, reconstruct state from canonical artifacts, the L/XL ledger, task
reports, and `git log`/diff—not conversation memory. Before transitioning to a
new gate, writing a dependent artifact, or dispatching execution, verify the
required artifact exists and has `status: approved` plus all approval metadata.
Never advance from a missing, malformed, or pending spec/plan. For execution,
the plan and its required L/XL spec must be approved before any task dispatch.
The ledger remains authoritative for completed, fixing, reviewing, and queued
tasks; preserve validation events and never convert skipped, unavailable,
failed, or not-run validation into passed. A completed fixer batch is not
releasable until its single combined review report is reconciled. Final handoff
or commit authorization is not available until the mandatory final branch review
report exists; the final review cannot be skipped. Review findings are
report-only, and the user chooses whether to fix, defer, or accept them without
automatic remediation or required acceptance metadata.
