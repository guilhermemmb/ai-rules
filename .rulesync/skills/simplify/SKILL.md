---
name: simplify
description: Simplifies code for clarity without changing behavior. Use for readability, maintainability, and complexity reduction after behavior is understood.
---

# Code Simplification

## Overview

Simplify code by reducing complexity while preserving exact behavior. The goal is not fewer lines - it's code that is easier to read, understand, modify, and debug. Every simplification must pass a simple test: "Would a new team member understand this faster than the original?"

## When to Use

- After a feature is working and tests pass, but the implementation feels heavier than it needs to be
- During code review when readability or complexity issues are flagged
- When you encounter deeply nested logic, long functions, or unclear names
- When refactoring code written under time pressure
- When consolidating related logic scattered across files
- After merging changes that introduced duplication or inconsistency

**When NOT to use:**

- Code is already clean and readable - don't simplify for the sake of it
- You don't understand what the code does yet - comprehend before you simplify
- The code is performance-critical and the "simpler" version would be measurably slower
- You're about to rewrite the module entirely - simplifying throwaway code wastes effort

## Operational Guidelines

- **Preserve behavior exactly.** Keep inputs, outputs, side effects, ordering,
  errors, and edge cases unchanged. If equivalence is uncertain, do not make
  the simplification.
- **Follow project conventions.** Read `AGENTS.md`, inspect neighboring code,
  and match local style for names, imports, control flow, errors, and types.
- **Prefer clarity over cleverness.** Use explicit control flow, meaningful
  names, and focused helpers when they reduce the reader's mental load.
- **Avoid over-simplification.** Keep abstractions that support testability or
  extensibility, and do not optimize for line count over comprehension.
- **Stay scoped.** Simplify recently changed code by default; avoid unrelated
  drive-by refactors unless explicitly requested.

## Process

### Step 1: Understand Before Touching

Before changing or removing anything, understand why it exists.

Answer:

- What is this code's responsibility?
- What calls it? What does it call?
- What are the edge cases and error paths?
- Are there tests that define expected behavior?
- Why might it have been written this way?

If you can't answer these, read more context first.

### Step 2: Look for Simplification Opportunities

Signals:

- Deep nesting
- Long functions with mixed responsibilities
- Nested ternaries
- Boolean flag arguments
- Repeated conditionals
- Generic or misleading names
- Duplicated logic
- Dead code
- Wrappers or abstractions that add no value

### Step 3: Apply Changes Incrementally

Make one simplification at a time.

For each simplification:

1. Make the change
2. Run relevant tests
3. Keep it only if behavior is preserved

Separate refactoring from feature work whenever possible.

### Step 4: Verify the Result

After simplifying, confirm:

- The code is genuinely easier to understand
- The diff is clean and reviewable
- Project conventions still match
- No behavior, error handling, or side effects changed

## Guidance for This Repository

- Prefer straightforward TypeScript over clever compression
- Preserve existing runtime behavior, tests, and hooks
- Favor explicit names and smaller focused helpers when they improve readability
- Keep refactors tightly scoped to the task or review feedback

## Verification Checklist

- [ ] Existing tests pass without modification
- [ ] Build/typecheck/lint still pass
- [ ] No unrelated files were refactored
- [ ] No error handling was weakened or removed
- [ ] The result is simpler to review than the original
