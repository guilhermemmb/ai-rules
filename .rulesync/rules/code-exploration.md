---
name: code-exploration
description: Centralized routing protocol for code discovery — RTK CLI for exact/local searches, Graph MCP for structural analysis
root: true
---

# Code Exploration Strategy

Use **RTK CLI tools** for exact/local discovery and **Graph MCP (codebase-memory-mcp)** for structural analysis. Choose the right tool for the task.

## Routing Decision Table

| Task | Preferred tool |
| :--- | :--- |
| Exact string, symbol, literal, or log search | `rtk grep` |
| Known-path localized read or signature inspection | `rtk read` |
| File discovery by pattern | `rtk find` |
| Dynamic templates, macros, or non-AST-friendly text | `rtk grep` / `rtk read` |
| Call hierarchy, implementations, inheritance, blast radius, architecture | Graph MCP |

## RTK Plugin

RTK is installed as an OpenCode plugin that transparently rewrites ordinary development commands before execution. `git status` automatically becomes `rtk git status` with no manual prefixing needed.

For **discovery**, use explicit RTK subcommands: `rtk grep`, `rtk read`, `rtk find`. These are separate from the transparent plugin rewrite.

Meta commands: `rtk gain` (savings), `rtk gain --history`, `rtk discover`, `rtk proxy <cmd>` (debug), `rtk --version`.

## Graph MCP (codebase-memory-mcp)

Use Graph MCP for multi-file structural questions: call hierarchies, implementations/inheritance, blast-radius impact analysis, architecture overviews. Targeted known-file reads do **not** require complex graph queries — use `rtk read` or direct Read for those.

Call `list_projects` first when the project identifier is unknown. Use the `display_name` or exact `name` returned.

Project name = absolute `root_path` slugified: replace `/` with `-`, drop leading `-`. e.g. `/Users/foo/developer/gorgias-chat` → `Users-foo-developer-gorgias-chat`.

### Tool selection by question

| Question shape | Graph MCP tool |
| :--- | :--- |
| High-level layout, unfamiliar codebase | `get_architecture` |
| Find symbol by name, concept, or regex | `search_graph` |
| Who calls this? What does it call? | `trace_path` |
| Read source for a specific symbol | `get_code_snippet` |
| Multi-hop patterns, aggregations, complexity | `query_graph` |
| Text search enriched with graph ranking | `search_code` |
| Map git diff to affected symbols | `detect_changes` |
| Project not indexed | `index_repository` |

## Fallback & Output Rules

- **Fall back immediately** to `rtk grep` / `rtk read` when Graph MCP results are empty or incomplete.
- **Do not use** unproxied `cat`, plain `grep`, or `ls` for discovery output. RTK-wrapped equivalents (`rtk grep`, `rtk read`, `rtk find`) produce token-efficient output.
- Plain `grep` / `cat` are allowed only when a dedicated diagnostic or shell pipeline genuinely requires raw output.
