Use the `codebase-memory-mcp` server to understand codebase structure without reading files one by one. It builds a persistent knowledge graph from source (tree-sitter across 158 languages, plus semantic type resolution for 12 including Python, TypeScript, Go, Rust, Java, PHP, C#, C/C++, Kotlin). Queries return in sub-milliseconds and cost ~99% fewer tokens than file-by-file exploration. All processing is local — code never leaves the machine.

Prefer it over raw grep/glob and over reading whole files when the question is about **where code lives, how it connects, or what an area looks like**: finding definitions, callers/callees, dependencies, routes, architecture, or impact of a change. Fall back to Read/grep only for exact line-level reading of a known file, or when a symbol is not yet indexed.

Do not use for: writing code, running tests, git operations, or fetching external library docs (use context7 for docs).

## Tools

**Discover & search**
- `search_graph` — primary entry point. Full-text `query` (natural language, BM25, camelCase-split) for discovery; `name_pattern` regex for exact matches; `semantic_query` (array of keywords) for vocabulary-bridging vector search. Narrow with `label`, `file_pattern`, `min_degree`. Paginate via `offset`/`limit` while `has_more` is true.
- `search_code` — graph-augmented text search: greps, then dedups matches into containing functions ranked by importance. Modes: `compact` (default), `full` (with source), `files`.
- `get_architecture` — high-level overview: packages, services, dependencies, routes, hotspots, layers, and `clusters` (Leiden community detection surfacing de-facto modules). Scope with `path`. Use first when orienting in an unfamiliar codebase.

**Trace & read**
- `trace_path` — follow edges. `calls` (callers/callees, `inbound`/`outbound`, depth 1-5), `data_flow` (value propagation with arg expressions), `cross_service` (through HTTP/async/gRPC/GraphQL Routes and CROSS_* cross-repo edges). Use for impact analysis and call chains instead of grepping for callers.
- `get_code_snippet` — read source for a symbol. First find the exact `qualified_name` via `search_graph`, then pass it here. This is a read tool, not a search tool.
- `query_graph` — read-only Cypher for multi-hop patterns, aggregations, cross-service analysis. Every Function/Method carries complexity properties (cyclomatic, cognitive, `loop_depth`, `transitive_loop_depth`, `linear_scan_in_loop`, `alloc_in_loop`, `recursive`) — query these to find hot-path/bottleneck candidates. Add `LIMIT` for broad queries (100k row ceiling).
- `get_graph_schema` / `detect_changes` — inspect node/edge types; map a git diff to affected symbols with risk classification.

**Manage**
- `index_repository` — build/update the graph. Modes: `full` (all files + similarity/semantic edges), `moderate`, `fast` (no similarity/semantic), `cross-repo-intelligence` (match Routes/Channels across projects). `persistence: true` writes a shareable `.codebase-memory/graph.db.zst`.
- `list_projects` / `index_status` / `delete_project` — manage indexed projects.
- `ingest_traces` / `manage_adr` — validate call edges with runtime traces; read/write Architecture Decision Records.

## Workflow

1. New or unfamiliar area → `get_architecture` (optionally scoped by `path`) to see the shape.
2. Find a symbol → `search_graph` with a natural-language `query`; grab the exact `qualified_name`.
3. Read it → `get_code_snippet` with that `qualified_name`.
4. Understand connections → `trace_path` (`calls` for who calls what, `cross_service` across services).
5. Complex/aggregate questions → `query_graph` with Cypher.
6. If a project is not indexed (`list_projects` doesn't show it), `index_repository` first.

## Notes

- Every tool takes a `project` argument — confirm the target project name with `list_projects` when unsure.
- Config lives in `.codebase-memory.json` (custom extensions) and `.cbmignore` (ignore rules). Env: `CBM_CACHE_DIR`, `CBM_WORKERS`, `CBM_ALLOWED_ROOT`, `CBM_LOG_LEVEL`.
- Repo: https://github.com/DeusData/codebase-memory-mcp
