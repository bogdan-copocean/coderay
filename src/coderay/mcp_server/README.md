# mcp_server

FastMCP server exposing four tools to AI coding assistants:

- `semantic_search` — meaning-based code search
- `get_file_skeleton` — file API surface (signatures, no bodies)
- `get_impact_radius` — blast radius of a change via graph BFS
- `index_status` — index health check

Entry point: `coderay-mcp` (stdio transport; `--sse` for development).
