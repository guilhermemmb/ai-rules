---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to EVERY project regardless of perceived simplicity.
</HARD-GATE>

## Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through this process. A todo list, a single-function utility, a config change — all of them. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences for truly simple projects), but you MUST present it and get approval.

## Checklist

You MUST complete each of these items in order:

1. **Explore project context** — dispatch @explorer to check files, docs, recent commits
2. **Research if needed** — dispatch @librarian for external docs, APIs, or library research
3. **Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria
4. **Propose 2-3 approaches** — with trade-offs and your recommendation; consult @oracle for architecture questions
5. **Present design** — in sections scaled to their complexity, get user approval after each section; dispatch @designer for UI-heavy sections
6. **Write design doc** — save to `docs/.planning/specs/YYYY-MM-DD-<topic>-design.md` and commit
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
Write design doc → docs/.planning/specs/YYYY-MM-DD-<topic>-design.md
    ↓
Spec self-review (fix inline)
    ↓
User reviews spec?
    ├── changes requested → revise → self-review again
    └── approved ↓
Load skill: writing-plans
```

**The terminal state is loading `writing-plans`.** Do NOT invoke any implementation skill directly. The ONLY skill you invoke after brainstorming is `writing-plans`.

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

- Write the validated design (spec) to `docs/.planning/specs/YYYY-MM-DD-<topic>-design.md`
- Commit the design document to git

**Spec Self-Review:**
After writing the spec document, look at it with fresh eyes:

1. **Placeholder scan:** Any "TBD", "TODO", incomplete sections, or vague requirements? Fix them.
2. **Internal consistency:** Do any sections contradict each other? Does the architecture match the feature descriptions?
3. **Scope check:** Is this focused enough for a single implementation plan, or does it need decomposition?
4. **Ambiguity check:** Could any requirement be interpreted two different ways? If so, pick one and make it explicit.

Fix any issues inline. No need to re-review — just fix and move on.

**User Review Gate:**
After the spec review passes, ask the user to review the written spec before proceeding:

> "Spec written and committed to `<path>`. Please review it and let me know if you want to make any changes before we start writing out the implementation plan."

Wait for the user's response. If they request changes, make them and re-run the spec review. Only proceed once the user approves.

**Implementation:**

- Load skill `writing-plans` to create a detailed implementation plan
- Do NOT invoke any other skill. `writing-plans` is the next step.

## Red Flags for Rationalizations

| Thought | Reality |
|---------|---------|
| "This is too simple for a design" | Simple projects are where unexamined assumptions cause the most waste. |
| "I need to explore first, then brainstorm" | Exploring IS part of brainstorming — dispatch @explorer as step 1. |
| "I can write a quick plan without a spec" | Specs prevent rework. Always spec → plan → execute. |
| "The user said just do it" | "Just do it" overrides SDD. If they said that, you may skip. Otherwise: spec first. |
