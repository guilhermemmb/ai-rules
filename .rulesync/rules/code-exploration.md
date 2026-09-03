---
name: code-exploration
description: Centralized routing protocol for code discovery — RTK/native tools, GitNexus, and Serena
root: true
---

# Code Exploration Strategy

Use the narrowest available inspection layer. RTK/native OpenCode tools remain
authoritative for exact/local work, shell, tests, Git, configuration,
documentation, and edits. GitNexus provides indexed, snapshot-based structural
analysis for Orchestrator, Oracle, Explorer, and Detective. Serena provides
live semantic inspection for Designer, Fixer, Reviewer-code, and Reviewer-types.
These integrations are not API-compatible substitutes for another tool; use
their documented operations and do not claim compatibility.

GitNexus is snapshot-based. GitNexus 1.6.5 exposes rename; this managed OpenCode
configuration denies the normalized `gitnexus_rename` tool. Agents must not
invoke mutation tools. Direct GitNexus processes outside managed OpenCode are not covered. Serena is read-only in its permanent grants. Native OpenCode tools
remain authoritative for files, shell, and edits. If an assigned index or
semantic service is unavailable, stale, empty, partial, truncated, ambiguous,
degraded, or returns `UNKNOWN`, treat the result as inconclusive and fall back
immediately to RTK/native tools.

## Routing Decision Table

| Task | Preferred tool |
| :--- | :--- |
| Exact string, symbol, literal, or log search | `rtk grep` |
| Known-path localized read or signature inspection | `rtk read` |
| File discovery by pattern | `rtk find` |
| Dynamic templates, macros, or non-AST-friendly text | `rtk grep` / `rtk read` |
| Definitions, references, implementations, diagnostics (assigned semantic agents) | Serena |
| Indexed architecture, processes, cross-repo/API impact, blast radius (assigned graph agents) | GitNexus |

## RTK Plugin

RTK is installed as an OpenCode plugin that transparently rewrites ordinary development commands before execution. `git status` automatically becomes `rtk git status` with no manual prefixing needed.

For **discovery**, use explicit RTK subcommands: `rtk grep`, `rtk read`, `rtk find`. These are separate from the transparent plugin rewrite.

Meta commands: `rtk gain` (savings), `rtk gain --history`, `rtk discover`, `rtk proxy <cmd>` (debug), `rtk --version`.

## GitNexus

Before graph work, inspect `gitnexus://repo/{name}/context` and confirm
freshness. Use `query` for unfamiliar concepts and flows, `context` for known
symbol relationships and known paths. Read affected process resources, inspect
schema before Cypher, and use `impact` before edits or dependency claims. Use
`detect_changes` before review or handoff. GitNexus 1.6.5 exposes rename; this
managed OpenCode configuration denies the normalized `gitnexus_rename` tool.
Agents must not invoke mutation tools. Direct GitNexus processes outside managed OpenCode are not covered.

GitNexus users follow: context/freshness → query/context → affected process
resources → impact → detect_changes. GitNexus indexing is explicit;
`gitnexus mcp` serves an existing registered index and does not build one.

## Serena

Serena users use the configured single project and check project/onboarding
status before substantive work. Prefer `get_symbols_overview`, `find_symbol`,
and `find_referencing_symbols`; read only the required symbol bodies. Serena
line numbers are 0-based. Do not duplicate native shell, file, grep, or patch
tools, and never invoke `prepare_for_new_conversation` unless explicitly
requested.

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
  or Serena results are unavailable or inconclusive.
- **Do not use** unproxied `cat`, plain `grep`, or `ls` for discovery output. RTK-wrapped equivalents (`rtk grep`, `rtk read`, `rtk find`) produce token-efficient output.
- Plain `grep` / `cat` are allowed only when a dedicated diagnostic or shell pipeline genuinely requires raw output.
