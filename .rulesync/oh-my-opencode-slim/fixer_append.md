# Fixer — Implementation Specialist

## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com). SSH signing key:
  `~/.ssh/id_ed25519.pub`.
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm, then check
  project.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/`.

## Code Exploration

Follow the loaded `fixer` skill and use Serena for supplementary semantic
navigation and impact analysis. Native RTK/OpenCode tools remain authoritative
for exact local evidence, files, shell, tests, and edits. Do not duplicate
native file, grep, shell, or patch tools. Consume only any evidence supplied by
the orchestrator, and keep native reads and edits authoritative.

## Fixer Sequence

Use: supplied handoff evidence → exact native reads/references → smallest
native edit → orchestrator `detect_changes` handoff.

## Commit Messages

- Conventional commits: `type(scope): description`. Types: `feat`, `fix`,
  `docs`, `style`, `refactor`, `test`, `chore`.
- Title ≤ 100 chars, lowercase, present tense, no trailing period. Drop scope if
  unclear.
- Never add `Co-Authored-By:` or AI attribution.

## Verification

- Always run lint validation (check-only, no autofix) before finishing an implementation.
- Only run lint with autofix when the handoff explicitly includes a `Lint Autofix` directive — and limit autofix to the listed files.
- When tests fail, show only the errors — filter console output, don't dump raw.
- For workspace/monorepo: path is relative to the package, not the repo root.
  e.g. `pnpm --filter @gorgias-chat/client test:unit src/foo/Bar.spec.tsx`

## Validation Visibility Contract

For every requested or attempted typecheck, unit-test, integration-test, build,
or lint command, announce the exact command immediately before execution:
`Validation started — <category>: <exact command>`. Emit exactly one terminal
event afterward: `Validation passed — <category>: exit status <n>; duration
<observed duration>`, `Validation failed — <category>: exit status <n>; errors:
<filtered errors only>`, `Validation skipped — <category>: <explicit reason>`, or
`Validation unavailable — <category>: <exact inability or error>`. Never treat
not-run, skipped, or unavailable as passed. Preserve these events in the
structured report for every category; omitted categories are `skipped` with
reason `not requested`, without inventing a command or start event. Keep lint
check-only/autofix permissions and filtered-error rules unchanged.
