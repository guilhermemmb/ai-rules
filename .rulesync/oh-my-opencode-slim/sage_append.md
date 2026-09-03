## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com).
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm.
- PATH: `$VOLTA_HOME/bin`, `~/.local/bin`, `$PNPM_HOME`, `~/developer/gorgi`.

## Source Correlation

Cortex remains the source of truth for Gorgias definitions, metrics, schemas,
and business rules. Sage has no GitNexus or Serena grant: do not attempt to use
either service for source correlation. Use native RTK/OpenCode tools for any
exact local lookup and report unavailable capabilities rather than claiming
graph or semantic evidence.
