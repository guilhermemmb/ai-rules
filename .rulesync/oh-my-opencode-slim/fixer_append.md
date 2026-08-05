# Fixer — Implementation Specialist

## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com). SSH signing key:
  `~/.ssh/id_ed25519.pub`.
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm, then check
  project.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/`.

## Code Exploration

Follow this routing: RTK CLI for exact/local discovery, Graph MCP for call hierarchies and structural analysis. Fall back to RTK immediately if Graph MCP returns empty/incomplete. See the loaded `fixer` skill for full discovery and bounded-work rules.

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
