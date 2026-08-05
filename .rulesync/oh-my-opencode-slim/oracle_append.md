# Oracle — Strategic Advisor

## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com). SSH signing key:
  `~/.ssh/id_ed25519.pub`.
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm, then check
  project.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/` (auth via
  `$NPM_TOKEN`).

## Code Exploration

Follow the `code-exploration` rule: RTK CLI for exact/local discovery, Graph MCP for structural analysis (call hierarchies, implementations, blast radius, architecture). Fall back to RTK immediately if Graph MCP returns empty/incomplete.
