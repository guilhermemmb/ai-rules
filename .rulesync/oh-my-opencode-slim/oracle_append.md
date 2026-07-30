# Oracle — Strategic Advisor

## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- RTK is active via plugin — commands are automatically optimized.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com). SSH signing key:
  `~/.ssh/id_ed25519.pub`.
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm, then check
  project.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/` (auth via
  `$NPM_TOKEN`).

## Codebase Memory MCP

**MANDATORY: use codebase-memory-mcp graph tools FIRST — before reading files.**

Call `list_projects` first when project name unknown.

**Tools:**

- `search_graph` — BM25 full-text, name_pattern regex, semantic_query vector.
  Narrow with label/file_pattern/min_degree.
- `search_code` — graph-augmented text search ranked by structural importance
- `get_architecture` — packages, services, routes, hotspots, clusters (Leiden
  community detection)
- `trace_path` — CALLS/DATA_FLOW/CROSS_SERVICE edges; impact analysis, call
  chains
- `get_code_snippet` — read source for a symbol (find qualified_name via
  search_graph first)
- `query_graph` — Cypher for multi-hop patterns, aggregations; complexity props:
  cyclomatic, cognitive, loop_depth, transitive_loop_depth, linear_scan_in_loop
- `get_graph_schema` / `detect_changes` — schema inspection; map git diff to
  affected symbols with risk classification
- `index_repository` / `list_projects` / `index_status` — manage indexed
  projects

**Project name** = absolute root_path slugified:
`/Users/foo/developer/gorgias-chat` → `Users-foo-developer-gorgias-chat`

Prefer codebase-memory-mcp over grep/glob for: definitions, callers/callees,
dependencies, routes, architecture, change impact. Fall back to Read/grep only
for exact line-level reads of known files.
