---
name: codebase-memory
description: AI rules/agent definition for codebase-memory.md
---

# Codebase Memory MCP

**MANDATORY: use Codebase Memory MCP graph tools FIRST — before reading files or
making code changes.**

Call `list_projects` first when project name unknown. Use `display_name` or
exact `name` returned.

```json
// Step 0 — discover project names
mcp_codebase-memo_list_projects()

// Step 1 — use the project identifier returned above
mcp_codebase-memo_get_architecture({ "project": "<display_name>" })
```

`codebase-memory-mcp` understands codebase structure without file-by-file reads.
Builds persistent knowledge graph from source (tree-sitter across 158 languages,
semantic type resolution for 12 including Python, TypeScript, Go, Rust, Java,
PHP, C#, C/C++, Kotlin). Queries return sub-millisecond, ~99% fewer tokens than
file exploration. All processing local — code never leaves machine.

Prefer over grep/glob and whole-file reads for: finding definitions,
callers/callees, dependencies, routes, architecture, change impact. Fall back to
Read/grep only for exact line-level reads of known files, or unindexed symbols.

Not for: writing code, running tests, git ops, external library docs (use
context7).

## Tools

**Discover & search**

- `search_graph(name_pattern, name_scope, label, file_pattern, exclude_file_pattern)`
  — primary entry point. Full-text `query` (natural language, BM25,
  camelCase-split); `name_pattern` regex for exact matches; `semantic_query`
  (keyword array) for vocabulary-bridging vector search. Narrow with `label`,
  `file_pattern`, `min_degree`. Paginate via `offset`/`limit` while `has_more`
  true.
- `search_code(pattern, project)` — graph-augmented text search: greps, dedupes
  matches into containing functions ranked by importance. Modes: `compact`
  (default), `full` (with source), `files`.
- `get_architecture(project)` — high-level overview: packages, services,
  dependencies, routes, hotspots, layers, `clusters` (Leiden community
  detection, de-facto modules). Scope with `path`. Use first in unfamiliar
  codebase.

**Trace & read**

- `trace_path(function_name, direction, depth)` — follow edges. `calls`
  (callers/callees, `inbound`/`outbound`, depth 1-5), `data_flow` (value
  propagation with arg expressions), `cross_service` (HTTP/async/gRPC/GraphQL
  Routes and CROSS\_\* cross-repo edges). Use for impact analysis, call chains —
  not grep.
- `get_code_snippet(qualified_name)` — read source for symbol. Find exact
  `qualified_name` via `search_graph` first, then pass here. Read tool, not
  search tool.
- `query_graph(query)` — read-only Cypher for multi-hop patterns, aggregations,
  cross-service analysis. Every Function/Method carries complexity properties
  (cyclomatic, cognitive, `loop_depth`, `transitive_loop_depth`,
  `linear_scan_in_loop`, `alloc_in_loop`, `recursive`) — query to find
  hot-path/bottleneck candidates. Add `LIMIT` for broad queries (100k row
  ceiling).
- `get_graph_schema(project)` / `detect_changes(project)` — inspect node/edge
  types; map git diff to affected symbols with risk classification.

**Manage**

- `index_repository(repo_path)` — build/update graph. Modes: `full` (all files +
  similarity/semantic edges), `moderate`, `fast` (no similarity/semantic),
  `cross-repo-intelligence` (match Routes/Channels across projects).
  `persistence: true` writes shareable `.codebase-memory/graph.db.zst`.
- `list_projects` — list indexed projects with node/edge counts.
- `index_status(project)` / `delete_project(project)` — check indexing status;
  remove project and graph data.
- `ingest_traces(traces)` / `manage_adr(action)` — validate call edges with
  runtime traces; read/write Architecture Decision Records.

## Workflow

1. `list_projects` — get correct project name.
2. `get_architecture(project)` (optionally scoped by `path`) — see shape.
3. Find symbol → `search_graph` with natural-language `query`; grab exact
   `qualified_name`.
4. Read it → `get_code_snippet` with that `qualified_name`.
5. Connections → `trace_path` (`calls` for who calls what, `cross_service`
   across services).
6. Complex/aggregate questions → `query_graph` with Cypher.
7. Use `read_file` only for exact raw content to edit specific line, or
   unindexed symbol.
8. Project not indexed (`list_projects` doesn't show it) → `index_repository`
   first.

## Notes

- Every tool takes `project` argument — confirm with `list_projects` when
  unsure.
- Project name = absolute `root_path` slugified: replace `/` with `-`, drop
  leading `-`. Applies to all projects, not just worktrees. e.g.
  `/Users/foo/developer/gorgias-chat` → `Users-foo-developer-gorgias-chat`.
- Config in `.codebase-memory.json` (custom extensions) and `.cbmignore` (ignore
  rules). Env: `CBM_CACHE_DIR`, `CBM_WORKERS`, `CBM_ALLOWED_ROOT`,
  `CBM_LOG_LEVEL`.
- Repo: https://github.com/DeusData/codebase-memory-mcp
