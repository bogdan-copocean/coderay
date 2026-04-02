# cli

Click-based CLI exposing all index operations.

Entry point: `coderay` (registered via `pyproject.toml`).

## Files

- `commands.py` — all commands: `init`, `build`, `watch`, `search`, `list`,
  `status`, `maintain`, `skeleton`, `graph`, `impact`
- `search_input.py` — `SearchInput` validates and normalises CLI/MCP search
  parameters into `SearchRequestDTO`; `resolve_result_paths` converts
  repo-relative paths to absolute paths for multi-repo workspaces

## Command summary

| Command | Description |
|---------|-------------|
| `init` | Create `.coderay.toml` and `.coderay/` in the current directory |
| `build [--full]` | Incremental update, or full rebuild with `--full` |
| `watch [--quiet]` | Re-index on file changes (recommended for active dev) |
| `search QUERY` | Semantic search; `--top-k`, `--path-prefix`, `--no-tests` |
| `list [--by-file]` | Show indexed chunks or per-file summary |
| `status` | Index state, branch, commit, chunk count, schema version |
| `maintain` | Compact fragments, reclaim space |
| `skeleton FILE` | Print signatures/docstrings; `--symbol` to filter to one class/function |
| `graph` | List call/import edges; `--from`, `--to`, `--kind` |
| `impact SYMBOL` | Blast radius of a symbol; bare name accepted if unambiguous |

See the root README for the full flag reference.
