## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com).
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm.
- PATH: `$VOLTA_HOME/bin`, `~/.local/bin`, `$PNPM_HOME`, `~/developer/gorgi`.

## Source Correlation

Follow `code-exploration` rule. Use Graph MCP only to map Gorgias metrics and business concepts back to code implementation — Cortex stays the source of truth for definitions. Prefer `rtk grep`/`rtk read` for exact symbol searches; fall back immediately if Graph MCP is empty/incomplete.
