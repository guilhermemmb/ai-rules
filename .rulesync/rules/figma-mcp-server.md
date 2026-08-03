---
description: Figma MCP Server connection configuration and tool reference (read-only scope)
globs: 
alwaysApply: false
---

# Figma MCP Server Reference

## Server Information

The Figma MCP server brings Figma design context directly into the AI workflow.

- **Name:** `com.figma.mcp/mcp`
- **Version:** 2.2.87
- **Source:** [github.com/figma/mcp-server-guide](https://github.com/figma/mcp-server-guide)
- **Connection URL:** `https://mcp.figma.com/mcp` (Streamable HTTP)
- **Local Desktop (alternative):** `http://127.0.0.1:3845/mcp`

### Connection Configuration

```json
{
  "mcpServers": {
    "figma": {
      "url": "https://mcp.figma.com/mcp"
    }
  }
}
```

For local Figma Desktop app access:
```json
{
  "mcpServers": {
    "figma-desktop": {
      "url": "http://127.0.0.1:3845/mcp"
    }
  }
}
```

### Authentication & Rate Limits

- Users with **Dev or Full seats** on Professional/Organization/Enterprise plans get per-minute rate limits (same as REST API Tier 1).
- **Starter plan or View/Collab seats**: limited to 6 tool calls per month.
- Verify identity and plan with the `whoami` tool.

## Read-Only Tool Catalog

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `get_design_context` | Primary spec collection tool. Returns structured React+Tailwind with layout, typography, colors, component structure, and contextual hints. | `fileKey`, `nodeId`, `format`, `query` |
| `get_metadata` | Sparse XML node map with IDs, names, dimensions. Use to navigate large files when `get_design_context` response is truncated. | `fileKey`, `nodeId` |
| `get_screenshot` | Visual reference screenshot of the selection. Source of truth for visual validation. | `fileKey`, `nodeId` |
| `get_variable_defs` | Variables and styles (colors, spacing, typography) from the selection. Maps Figma tokens to project tokens. | `fileKey`, `nodeId` |
| `get_code_connect_suggestions` | Identifies unmapped published components for Code Connect. Returns component names, properties, thumbnails. | `fileKey`, `nodeId`, `excludeMappingPrompt` |
| `get_code_connect_map` | Retrieves existing Figma node → code component mappings. | `fileKey`, `nodeId` |
| `get_context_for_code_connect` | Fetches Figma component property definitions for creating `.figma.ts` templates. | `fileKey`, `nodeId`, `clientFrameworks`, `clientLanguages` |
| `get_motion_context` | Animation/motion data: keyframes, easing, timing, timeline cohorts. Use with `recursive: true`. | `fileKey`, `nodeId`, `recursive` |
| `get_figjam` | FigJam inspection tool. Returns full node tree as XML. Only way to discover node IDs in FigJam files. | `fileKey`, `nodeId` |
| `whoami` | Returns authenticated user identity and plan information. | — |
| `search_design_system` | Search linked design system libraries for components, variables, and styles. | `query` |
| `get_libraries` | Discover available design system libraries. | — |

## Tools NOT in Scope for Spec Collection

These tools are **write or generation tools** — not needed for read-only spec collection:

- `use_figma` — Execute Plugin API JavaScript to write/mutate Figma nodes
- `generate_figma_design` — Create Figma designs from UI descriptions
- `create_new_file` — Create blank Figma/FigJam/Slides files
- `generate_diagram` — Create FigJam diagrams from Mermaid syntax
- `upload_assets` — Upload images/blobs to Figma files
- `send_code_connect_mappings` — Write Code Connect mappings back to Figma
- `add_code_connect_map` — Establish new Figma → code mappings
- `create_design_system_rules` — Generate project-specific rules

## URL Parsing Reference

| URL Format | fileKey | nodeId |
|---|---|---|
| `figma.com/design/:fileKey/:name?node-id=X-Y` | `:fileKey` | `X-Y` → `X:Y` |
| `figma.com/file/:fileKey/:name?node-id=X-Y` | `:fileKey` | `X-Y` → `X:Y` |
| `figma.com/design/:fileKey/branch/:branchKey/:name` | use `:branchKey` | from `node-id` param |

**Critical:** Always convert `nodeId` hyphens to colons when calling MCP tools: `1234-5678` → `1234:5678`.

## Official Documentation

- [Figma MCP Server Documentation](https://developers.figma.com/docs/figma-mcp-server/)
- [Figma MCP Server Tools and Prompts](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/)
- [Figma Variables and Design Tokens](https://help.figma.com/hc/en-us/articles/15339657135383-Guide-to-variables-in-Figma)
