# Commit / Push Safety Scan

On-demand checklist. Read and apply this before any `git commit`, `git push`, or
`git rebase` (also on branch switch, and when working on a branch with an open
PR). It is intentionally kept out of always-loaded context — load it only when
one of those triggers fires.

If ANY red flag is found: **STOP**, show the exact `file:line` with context,
explain what looks wrong, and ask before proceeding.

## What to look for

1. **Mock / test data & hardcoded payloads** — mock API responses, dummy data
   arrays/objects, sample payloads, early returns with hardcoded data
   (`res.send([{…}])`, `return [{…}]`).
2. **Debug return values** — hardcoded `return true` / `return false`, bypassed
   feature flags or conditionals, short-circuit returns, functions that ignore
   their own logic.
3. **Cleanup leftovers** — 3+ unused imports in one file (strong signal of an
   unfinished debug session), commented-out code blocks, unused vars/functions,
   dead code paths.
4. **Sensitive hardcoded values** — API keys, tokens, passwords, credentials,
   internal URLs, DB connection strings, hardcoded user ids/emails, debug flags
   set to `true`, `console.log` with sensitive data.
5. **Development artifacts** — temporary debug code, dev-only flags, hardcoded
   env values.

## Search keywords in the diff

`return true` / `return false` (esp. when they ignore the logic above) ·
`res.send([` · `res.json([` / `res.json({` · `mock` / `dummy` / `fake` /
`hardcode` · `TODO` / `FIXME` / `HACK` / `XXX` · `console.log` / `console.warn`
/ `debugger` · large object/array literals (>3 lines) in returns/responses ·
lines starting with `// ` (commented code) · imports from `/mocks/`,
`/fixtures/`, `/test-utils/` in production code.

## Process

1. `git diff --staged` (or the relevant commit range) to review changes.
2. Scan each changed file against the categories and keywords above.
3. On any hit: STOP, report `file:line`, ask for confirmation.

## Proceed without confirmation only if

- Changes are in test files (`*.test.*`, `*.spec.*`, `__tests__/`,
  `*.stories.*`).
- Mock data lives in designated dirs (`__mocks__/`, `fixtures/`, `test-data/`).
- The file is clearly a config/constant file meant to hold sample data.
- Unused imports are part of a refactor a linter will clean up.
- The user has explicitly confirmed the code is intentional.

## Dev-mode pattern for intentional mock/debug code

Never commit raw mock code. Always gate it behind a development-mode env check
so it can't run in production. Use the project's own dev-mode signal (check the
project's CLAUDE.md / `.rulesync` for the exact env var — e.g. a backend
`NODE_ENV` check vs. a frontend build-env check).

```typescript
// ❌ BAD — naked mock response
export const getThings = async (req, res) => {
  res.json([{ id: 1, name: "Sample" }]);
};

// ✅ GOOD — gated behind the project's dev-mode check
export const getThings = async (req, res) => {
  if (isDevMode) {
    return res.json([{ id: 1, name: "Sample" }]);
  }
  res.json(await db.things.findAll());
};
```
