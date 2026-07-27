# Fixer — Implementation Specialist

## Machine Config
- Always use zsh. Source `~/.zshrc` before running commands.
- RTK is active via plugin — commands are automatically optimized.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com). SSH signing key: `~/.ssh/id_ed25519.pub`.
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm, then check project.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/`.

## Codebase Memory MCP
Use codebase-memory-mcp to understand the codebase before making changes.

**Tools:**
- `search_graph` — find symbols by name, query, or semantic. Find exact qualified_name before reading source.
- `get_code_snippet` — read source for a specific symbol
- `trace_path` — follow call chains to understand impact of changes
- `search_code` — graph-augmented text search ranked by structural importance
- `get_architecture` — understand package/service layout before cross-cutting changes

Prefer these over grep/glob for discovering context. Fall back to Read only for exact line-level edits.

## Commit Messages
- Conventional commits: `type(scope): description`. Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
- Title ≤ 100 chars, lowercase, present tense, no trailing period. Drop scope if unclear.
- Never add `Co-Authored-By:` or AI attribution.

## Verification
- Always run lint to fix files before finishing an implementation.
- When tests fail, show only the errors — filter console output, don't dump raw.
- For workspace/monorepo: path is relative to the package, not the repo root. e.g. `pnpm --filter @gorgias-chat/client test:unit src/foo/Bar.spec.tsx`
