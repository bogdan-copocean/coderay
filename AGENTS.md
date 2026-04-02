# CodeRay — agent guidance

This project has a CodeRay MCP server available. Use it to navigate the codebase
efficiently instead of reading full files.

**Reading files is expensive.** A 400-line file costs ~3,600 tokens. Its skeleton
costs ~830. A targeted `semantic_search` result costs ~400. Prefer CodeRay lookups
over full-file reads wherever the question is about structure, intent, or dependency.

## MCP tools

| Tool | When to use |
|------|-------------|
| `semantic_search` | "How/where" questions — intent-based lookup across the whole index |
| `get_file_skeleton` | Before reading a file — get all signatures and docstrings without bodies |
| `get_impact_radius` | Before refactoring — see every caller and dependent of a function or class |
| `coderay://index/status` | Check the index is fresh before relying on results |

## CLI tools (for humans)

| Command | When to use |
|---------|-------------|
| `coderay search "query"` | Same as `semantic_search` — intent-based lookup from the terminal |
| `coderay skeleton FILE` | Same as `get_file_skeleton` — print signatures without bodies |
| `coderay impact SYMBOL` | Same as `get_impact_radius` — blast radius from the terminal |
| `coderay status` | Check index freshness before relying on results |

## CodeRay is an augmentation, not a replacement for grep

- **Exact symbol or string lookup** → use grep/ripgrep. It is faster and more precise.
- **Intent-based questions** ("where is retry logic", "how is config loaded") → use `semantic_search`.
- **File API surface** → use `get_file_skeleton` before deciding to read the full source.
- **Dependency analysis** → use `get_impact_radius` before touching a function.
- **"Which files import this module?"** → grep is fine. **"What calls this method across subclasses?"** → `get_impact_radius`.

## When the index might be stale

Results can be stale if files changed since the last build. Signs of staleness:
- `semantic_search` returns results that don't match the current code
- `get_impact_radius` shows no callers for something that's clearly used
- `index_status` shows an old commit or `INCOMPLETE` state

Ask the user to run `coderay build` (or `coderay watch` if not already running) to refresh.

## Node ID format for `get_impact_radius`

```
src/models.py::User.save     # class method
src/utils.py::parse_config   # top-level function
parse_config                 # bare name — works if unambiguous in the graph
```

If a bare name is ambiguous the tool returns a list of candidates to choose from.

## Multi-repo workspaces

CodeRay can index multiple repositories under one index. Each repo has an alias
defined in `.coderay.toml`. Pass `repos: ["my-service"]` to `semantic_search` to
scope results to one repo, or `repos: ["*"]` for workspace-wide search.
Default scope is set by `search.default_scope` in the config.

## Monorepo / subtree indexing

Each `[[index.roots]]` entry accepts an optional `include` list to restrict indexing
to specific subdirectories. Only files under those paths are indexed and searched.

## Automatic deindexing

`.coderay.toml` is the source of truth for what belongs in the index. If a file is
deleted, its path is removed from `include`, or it matches a new `exclude_patterns`
entry — it is automatically removed from the index on the next build or watch cycle.

## Source of truth

All behaviour — what to index, what to exclude, search tuning, embedding backend —
is in `.coderay.toml` at the project root. If something seems off, check the config
there first, then run `coderay status` to verify the index reflects it.
