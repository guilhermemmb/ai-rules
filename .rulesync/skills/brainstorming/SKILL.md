---
name: brainstorming
description: "Use this for L/XL work after T-shirt sizing. Explores user intent, requirements and design before implementation."
---

# Brainstorming L/XL Work Into Designs

Use this only when the orchestrator has selected the L/XL design/spec workflow.
The single planning-state contract is `.rulesync/rules/planning-state.md`;
consume its mode and approval rules without reclassifying the work.

Understand the project, ask one question at a time, present the design, and get
user approval before creating an approved spec.

<HARD-GATE>
For L/XL work, do NOT invoke any implementation skill, write any code, scaffold
any project, or take any implementation action until you have presented a
separate design/spec and the user has approved it. This gate does not apply to
XS or the approved S/M combined-plan path.
</HARD-GATE>

## Checklist

Complete these items in order:

1. **Explore project context** — dispatch @explorer to check files, docs, and recent commits.
2. **Research if needed** — dispatch @librarian for external docs, APIs, or library research.
3. **Ask clarifying questions** — ask one question per message about purpose, constraints, and success criteria.
4. **Propose approaches** — present 2–3 options with trade-offs and a recommendation; consult @oracle for architecture questions.
5. **Present design** — scale sections to complexity, get user approval, and dispatch @designer for UI-heavy sections.
6. **Write design doc** — save a `pending` artifact under the canonical `specs/` directory; include the persisted approval metadata required by `.rulesync/rules/planning-state.md` and do not commit it.
7. **Self-review** — check placeholders, contradictions, ambiguity, and scope.
8. **User review** — ask the user to review the written spec and revise it if requested.
9. **Persist approval** — after approval, update the same artifact to `status: approved` with approver, RFC 3339 approval timestamp, and durable approval evidence; only then load `writing-plans`.

For an oversized request, decompose it before continuing. Prefer the smallest
viable approach and involve specialists only when needed. The next skill after
an approved L/XL spec is `writing-plans`; do not invoke an implementation skill
directly.

## User Review Gate

After self-review, ask:

> "Spec written to `<path>`. Please review it and let me know if you want to make any changes before we start writing out the implementation plan."

Wait for the user's response. If changes are requested, revise and repeat the
self-review. Do not load `writing-plans` until the approval metadata is
persisted as `approved`.

## Red Flags for Rationalizations

| Thought | Reality |
|---|---|
| "This L/XL work is too simple for a design" | The selected L/XL workflow requires the full design gate. |
| "I need to explore first, then brainstorm" | Exploring is step 1 of brainstorming — dispatch @explorer. |
| "I can write a quick plan without a spec for L/XL work" | L/XL requires approved spec -> approved plan -> execute; S/M uses the combined plan. |
| "The user said just do it" | Follow the orchestrator-selected workflow and its approval gate. |
