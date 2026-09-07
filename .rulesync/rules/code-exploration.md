---
name: code-exploration
description: Centralized routing protocol for code discovery — RTK/native tools
root: true
---

# Code Exploration Strategy

Use the narrowest available inspection layer. RTK/native OpenCode tools remain
authoritative for exact/local work, shell, tests, Git, configuration,
documentation, and edits. Native OpenCode tools are authoritative for exact
and local inspection across all agents.

## Routing Decision Table

| Task | Preferred tool |
| :--- | :--- |
| Exact string, symbol, literal, or log search | `rtk grep` |
| Known-path localized read or signature inspection | `rtk read` |
| File discovery by pattern | `rtk find` |
| Dynamic templates, macros, or non-AST-friendly text | `rtk grep` / `rtk read` |
| Exact definitions, references, implementations, diagnostics | `rtk grep` / `rtk read` |

## RTK Plugin

RTK is installed as an OpenCode plugin that transparently rewrites ordinary development commands before execution. `git status` automatically becomes `rtk git status` with no manual prefixing needed.

For **discovery**, use explicit RTK subcommands: `rtk grep`, `rtk read`, `rtk find`. These are separate from the transparent plugin rewrite.

Meta commands: `rtk gain` (savings), `rtk gain --history`, `rtk discover`, `rtk proxy <cmd>` (debug), `rtk --version`.

## Fallback & Output Rules

- Use `rtk grep` / `rtk read` / `rtk find` for exact discovery and inspection.
- **Do not use** unproxied `cat`, plain `grep`, or `ls` for discovery output. RTK-wrapped equivalents (`rtk grep`, `rtk read`, `rtk find`) produce token-efficient output.
- Plain `grep` / `cat` are allowed only when a dedicated diagnostic or shell pipeline genuinely requires raw output.
