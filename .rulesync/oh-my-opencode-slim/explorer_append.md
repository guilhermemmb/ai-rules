# Explorer — Codebase Reconnaissance

## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/`.

## Code Exploration

Follow the `code-exploration` rule: RTK CLI (`rtk grep`, `rtk read`, `rtk find`) for exact/local discovery; Graph MCP for call hierarchies, implementations, blast radius, architecture. Fall back to RTK immediately if Graph MCP returns empty or incomplete results.
