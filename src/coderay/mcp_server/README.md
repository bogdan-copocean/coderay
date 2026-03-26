# mcp_server

FastMCP server exposing three tools and one resource to AI coding assistants:

- `semantic_search` — meaning-based code search
- `get_file_skeleton` — file API surface (signatures, no bodies)
- `get_impact_radius` — blast radius of a change via graph BFS
- `index_status` — index health check (resource)

Entry point: `coderay-mcp` (stdio transport).

## Configuration

Set `CODERAY_REPO_ROOT` in the MCP server's `env` so it finds `.coderay.toml` and the `.coderay/` index:

```json
"env": { "CODERAY_REPO_ROOT": "${workspaceFolder}" }
```

Cursor interpolates `${workspaceFolder}`. Run `coderay init` then `coderay build` (or `coderay watch`) from the project root first.
