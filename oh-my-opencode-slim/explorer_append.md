# Explorer — Codebase Reconnaissance

## Machine Config
- Always use zsh. Source `~/.zshrc` before running commands.
- RTK is active via plugin — commands are automatically optimized.
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/`.

## Codebase Memory MCP
**MANDATORY: use codebase-memory-mcp graph tools FIRST — before reading files.**

Call `list_projects` first when project name unknown.

**Tools (use in order of preference):**
- `get_architecture` — start here for unfamiliar codebases; packages, services, routes, hotspots, Leiden clusters
- `search_graph` — find symbols by natural language query, regex name_pattern, or semantic_query vectors. Paginate with offset/limit while has_more is true.
- `search_code` — graph-augmented grep, deduped into functions ranked by importance
- `trace_path` — follow CALLS (inbound/outbound), DATA_FLOW (value propagation), CROSS_SERVICE (HTTP/async/gRPC across repos)
- `get_code_snippet` — read source for a symbol (find exact qualified_name via search_graph first)
- `query_graph` — Cypher for multi-hop patterns; complexity: transitive_loop_depth, linear_scan_in_loop, alloc_in_loop
- `detect_changes` — map git diff to affected symbols with risk classification
- `index_repository` — build/update graph when project not indexed

**Project name** = absolute root_path slugified. e.g. `/Users/foo/developer/gorgias-chat` → `Users-foo-developer-gorgias-chat`

Prefer all of the above over grep/glob for broad exploration. Fall back to Read/grep only for exact line-level content of known files.
