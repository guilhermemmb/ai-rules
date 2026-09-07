---
name: brainstorming
description: "Use this for L/XL work after T-shirt sizing. Explores user intent, requirements and design before implementation."
---

# Brainstorming L/XL Work Into Designs

Use this only for L/XL work after the orchestrator has shown the scale
`T-shirt size: XS | S | M | L | XL`, the selected size, and its rationale. XS
executes immediately; S/M use the combined SDD + implementation-plan format in
`writing-plans` without a separate design spec.

Start by understanding the current project context, then ask questions one at a
time to refine the idea. Once you understand what you're building, present the
design and get user approval.

<HARD-GATE>
For L/XL work, do NOT invoke any implementation skill, write any code, scaffold
any project, or take any implementation action until you have presented a
separate design/spec and the user has approved it. This gate does not apply to
XS or the approved S/M combined-plan path.
</HARD-GATE>

## Anti-Pattern: Bypassing Design for L/XL Work

L/XL projects require this process even when an individual change looks simple.
S/M projects must not be expanded into a separate design spec.

## Checklist

For L/XL work, you MUST complete each of these items in order:

1. **Explore project context** — dispatch @explorer to check files, docs, recent commits
2. **Research if needed** — dispatch @librarian for external docs, APIs, or library research
3. **Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria
4. **Propose 2-3 approaches** — with trade-offs and your recommendation; consult @oracle for architecture questions
5. **Present design** — in sections scaled to their complexity, get user approval after each section; dispatch @designer for UI-heavy sections
6. **Write design doc** — save to `~/developer/planning-docs/{{repository-name}}/.planning/specs/YYYY-MM-DD-<topic>-design.md`; do not commit it in this workflow
7. **Spec self-review** — quick inline check for placeholders, contradictions, ambiguity, scope
8. **User reviews written spec** — ask user to review the spec file before proceeding
9. **Transition to implementation** — load skill `writing-plans` to create the implementation plan

## Process Flow

```
Explore project context (@explorer)
    ↓
Research if needed (@librarian, @oracle for architecture)
    ↓
Ask clarifying questions (one at a time)
    ↓
Propose 2-3 approaches with trade-offs
    ↓
Present design sections → User approves?
    ├── no, revise → back to Present design sections
    └── yes ↓
Write design doc → ~/developer/planning-docs/{{repository-name}}/.planning/specs/YYYY-MM-DD-<topic>-design.md
    ↓
Spec self-review (fix inline)
    ↓
User reviews spec?
    ├── changes requested → revise → self-review again
    └── approved ↓
Load skill: writing-plans
```

**The terminal state is loading `writing-plans`.** Do NOT invoke any
implementation skill directly. The ONLY skill you invoke after L/XL
brainstorming is `writing-plans`, and only after the separate spec is approved.

## The Process

**Understanding the idea:**

- Dispatch @explorer to check out the current project state first (files, docs, recent commits)
- Before asking detailed questions, assess scope: if the request describes multiple independent subsystems (e.g., "build a platform with chat, file storage, billing, and analytics"), flag this immediately. Don't spend questions refining details of a project that needs to be decomposed first.
- If the project is too large for a single spec, help the user decompose into sub-projects: what are the independent pieces, how do they relate, what order should they be built? Then brainstorm the first sub-project through the normal design flow. Each sub-project gets its own spec → plan → implementation cycle.
- For appropriately-scoped projects, ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message — if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**

- Propose 2-3 different approaches with trade-offs
- For architecture questions, dispatch @oracle for an independent strategic assessment
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why
- YAGNI ruthlessly — remove unnecessary features from every approach and design

**Presenting the design:**

- Once you believe you understand what you're building, present the design
- Scale each section to its complexity: a few sentences if straightforward, up to 200-300 words if nuanced
- Ask after each section whether it looks right so far
- Cover: architecture, components, data flow, error handling, testing
- For UI/UX-heavy sections, dispatch @designer for design options and mockup direction
- Be ready to go back and clarify if something doesn't make sense

**Design for isolation and clarity:**

- Break the system into smaller units that each have one clear purpose, communicate through well-defined interfaces, and can be understood and tested independently
- For each unit, you should be able to answer: what does it do, how do you use it, and what does it depend on?
- Can someone understand what a unit does without reading its internals? Can you change the internals without breaking consumers? If not, the boundaries need work.
- Smaller, well-bounded units are also easier to work with — you reason better about code you can hold in context at once.

**Working in existing codebases:**

- Always dispatch @explorer before proposing changes. Follow existing patterns.
- Where existing code has problems that affect the work (e.g., a file that's grown too large, unclear boundaries, tangled responsibilities), include targeted improvements as part of the design.
- Don't propose unrelated refactoring. Stay focused on what serves the current goal.

## After the Design

**Documentation:**

- Write the validated design (spec) to `~/developer/planning-docs/{{repository-name}}/.planning/specs/YYYY-MM-DD-<topic>-design.md`
- Do not commit the design document in this workflow

**Spec Self-Review:**
After writing the spec document, look at it with fresh eyes:

1. **Placeholder scan:** Any "TBD", "TODO", incomplete sections, or vague requirements? Fix them.
2. **Internal consistency:** Do any sections contradict each other? Does the architecture match the feature descriptions?
3. **Scope check:** Is this focused enough for a single implementation plan, or does it need decomposition?
4. **Ambiguity check:** Could any requirement be interpreted two different ways? If so, pick one and make it explicit.

Fix any issues inline. No need to re-review — just fix and move on.

**User Review Gate:**
After the spec review passes, ask the user to review the written spec before proceeding:

> "Spec written to `<path>`. Please review it and let me know if you want to make any changes before we start writing out the implementation plan."

Wait for the user's response. If they request changes, make them and re-run the spec review. Only proceed once the user approves.

**Implementation:**

- Load skill `writing-plans` to create a detailed implementation plan
- Do NOT invoke any other skill. `writing-plans` is the next step.

## Red Flags for Rationalizations

| Thought | Reality |
|---------|---------|
| "This L/XL work is too simple for a design" | L/XL work requires the full design gate. |
| "I need to explore first, then brainstorm" | Exploring IS part of brainstorming — dispatch @explorer as step 1. |
| "I can write a quick plan without a spec for L/XL work" | L/XL work requires spec → plan → execute; S/M work uses the combined plan. |
| "The user said just do it" | The T-shirt size still must be shown; XS executes immediately, while S/M/L/XL follow their approval gates. |
