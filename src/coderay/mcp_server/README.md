# mcp_server

FastMCP server exposing CodeRay to AI coding assistants over stdio.

Entry point: `coderay-mcp` (registered via `pyproject.toml`).

## Tools

| Tool | Requires index | Description |
|------|---------------|-------------|
| `semantic_search` | Yes | Meaning-based search with optional repo scoping, path prefix, test filtering |
| `get_file_skeleton` | No | Signatures and docstrings only — no bodies |
| `get_impact_radius` | Yes | Reverse BFS from a symbol; bare name accepted if unambiguous |
| `coderay://index/status` | Yes | Index health: state, branch, commit, chunk count (resource) |

## Configuration

Set `CODERAY_REPO_ROOT` in the MCP server's `env` so it finds `.coderay.toml`
and the `.coderay/` index:

```json
{
  "mcpServers": {
    "coderay": {
      "command": "/path/to/.venv/bin/coderay-mcp",
      "env": { "CODERAY_REPO_ROOT": "${workspaceFolder}" }
    }
  }
}
```

Run `coderay init` then `coderay build` (or `coderay watch`) from the project
root before starting the MCP server.

## Design notes

- `Retrieval` and `StateMachine` instances are cached per index directory to
  avoid re-initialising on every tool call.
- All tools are read-only (`readOnlyHint: true`).
- The server instructs the assistant that CodeRay augments grep — exact symbol
  lookup should still use ripgrep.
