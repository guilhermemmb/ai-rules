---
name: code-exploration
description: Centralized routing protocol for code discovery — RTK/native tools and GitNexus
root: true
---

# Code Exploration Strategy

Use the narrowest available inspection layer. RTK/native OpenCode tools remain
authoritative for exact/local work, shell, tests, Git, configuration,
documentation, and edits. GitNexus provides indexed, snapshot-based structural
analysis only for Orchestrator, Oracle, Explorer, and Detective. All other
agents use native OpenCode tools for exact and local inspection; these
integrations are not API-compatible substitutes for one another, so use only
documented operations and do not claim unavailable access.

GitNexus is snapshot-based. GitNexus 1.6.5 exposes server-side `rename`; this
managed OpenCode configuration denies the normalized `gitnexus_rename` tool.
Agents must not invoke mutation tools. Direct GitNexus processes outside
managed OpenCode are not covered. Native OpenCode tools remain authoritative
for files, shell, and edits. If GitNexus is unavailable, stale, empty,
partial, truncated, ambiguous, degraded, or returns `UNKNOWN`, treat the
result as inconclusive and fall back immediately to RTK/native tools.

## Routing Decision Table

| Task | Preferred tool |
| :--- | :--- |
| Exact string, symbol, literal, or log search | `rtk grep` |
| Known-path localized read or signature inspection | `rtk read` |
| File discovery by pattern | `rtk find` |
| Dynamic templates, macros, or non-AST-friendly text | `rtk grep` / `rtk read` |
| Exact definitions, references, implementations, diagnostics | `rtk grep` / `rtk read` |
| Indexed architecture, processes, cross-repo/API impact, blast radius (assigned graph agents) | GitNexus |

## RTK Plugin

RTK is installed as an OpenCode plugin that transparently rewrites ordinary development commands before execution. `git status` automatically becomes `rtk git status` with no manual prefixing needed.

For **discovery**, use explicit RTK subcommands: `rtk grep`, `rtk read`, `rtk find`. These are separate from the transparent plugin rewrite.

Meta commands: `rtk gain` (savings), `rtk gain --history`, `rtk discover`, `rtk proxy <cmd>` (debug), `rtk --version`.

## GitNexus

Before graph work, inspect `gitnexus://repo/{name}/context` and confirm
freshness. GitNexus users follow this sequence:

`context/freshness → query/context → affected process resources → impact → detect_changes`

Use `query` for unfamiliar concepts and flows, `context` for known symbol
relationships and known paths, and read affected process resources for workflow
semantics. Inspect the schema before Cypher. Use `impact` before edits or
dependency claims and `detect_changes` before review or handoff. GitNexus
indexing is explicit; `gitnexus mcp` serves an existing registered index and
does not build one.

GitNexus 1.6.5 exposes server-side `rename`, while this managed OpenCode
configuration denies the normalized `gitnexus_rename` tool. Agents must not
invoke mutation tools; direct GitNexus processes outside managed OpenCode are
not covered. Treat stale, empty, partial, truncated, ambiguous, degraded, or
`UNKNOWN` results as inconclusive and fall back immediately to native
RTK/OpenCode tools.

### GitNexus tool selection by question

| Question shape | GitNexus operation |
| :--- | :--- |
| Unfamiliar concept or flow | `query` |
| Known symbol relationships | `context` |
| Known symbol/data relationship | `context` |
| Dependency or edit blast radius | `impact` |
| Review or handoff changes | `detect_changes` |
| Complex graph query | `query` after schema inspection |

## Fallback & Output Rules

- Fall back immediately to `rtk grep` / `rtk read` / `rtk find` when GitNexus
  results are unavailable or inconclusive.
- **Do not use** unproxied `cat`, plain `grep`, or `ls` for discovery output. RTK-wrapped equivalents (`rtk grep`, `rtk read`, `rtk find`) produce token-efficient output.
- Plain `grep` / `cat` are allowed only when a dedicated diagnostic or shell pipeline genuinely requires raw output.
