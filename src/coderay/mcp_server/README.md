# mcp_server

FastMCP server exposing three tools and one resource to AI coding assistants:

- `semantic_search` — meaning-based code search
- `get_file_skeleton` — file API surface (signatures, no bodies)
- `get_impact_radius` — blast radius of a change via graph BFS
- `index_status` — index health check (resource)

Entry point: `coderay-mcp` (stdio transport).

## Configuration

Set `CODERAY_INDEX_DIR` in the MCP server's `env` so it finds the index and graph:

```json
"env": { "CODERAY_INDEX_DIR": "${workspaceFolder}/.index" }
```

Cursor interpolates `${workspaceFolder}`. Without this, the server may use the wrong working directory and fail to load the index.
