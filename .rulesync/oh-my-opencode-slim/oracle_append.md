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

Follow the `code-exploration` rule and use GitNexus only for its indexed
architecture surface. GitNexus is snapshot-based. GitNexus 1.6.5 exposes rename;
this managed OpenCode configuration denies the normalized `gitnexus_rename` tool.
Agents must not invoke mutation tools. Direct GitNexus processes outside managed
OpenCode are not covered. Start with `gitnexus://repo/{name}/context` and verify
freshness. Follow this sequence: context/freshness -> query/context -> affected process resources -> impact -> detect_changes -> exact symbol verification. Use
`query` for unfamiliar concepts, `context` for relationships, and affected
process resources for workflow semantics. Use `impact` before dependency claims
or edits, inspect schema before Cypher, and verify exact symbols with native
tools before making a recommendation. Treat stale, empty, partial, truncated,
ambiguous, degraded, or `UNKNOWN` results as inconclusive.

## Oracle Sequence

Use: context/freshness -> query/context -> affected process resources -> impact -> detect_changes -> exact symbol verification. Native RTK/OpenCode reads remain
authoritative. GitNexus is snapshot-based, so do not claim more than its current
evidence.
