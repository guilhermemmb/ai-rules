# Explorer — Codebase Reconnaissance

## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/`.

## Code Exploration

Follow the `code-exploration` rule. For unfamiliar concepts or flows, use
GitNexus in this order: GitNexus context/freshness -> query/context -> affected process resources -> impact -> detect_changes. Inspect schema before Cypher.
Treat stale, empty, partial, truncated, ambiguous, degraded, or `UNKNOWN`
results as inconclusive and fall back immediately to native RTK/OpenCode tools.
Native RTK/OpenCode tools remain authoritative for exact files, shell, and
edits. GitNexus 1.6.5 exposes rename; this managed OpenCode configuration
denies the normalized `gitnexus_rename` tool. Agents must not invoke mutation tools. Direct GitNexus processes outside managed OpenCode are not covered.

## Explorer Sequence

Use GitNexus context/freshness -> query/context -> affected process resources -> impact -> detect_changes. Explorer has GitNexus only and must not claim Serena access. Keep native RTK/OpenCode tools authoritative for exact files, shell, and edits.
