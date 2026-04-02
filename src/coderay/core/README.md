# core

Shared foundations used across all modules.

- `config.py` — TOML config loading with defaults and deep merge.
  `.coderay.toml` is the source of truth; `get_config()` returns a cached
  `Config`. `IndexRootEntry.include` restricts a root to specific subtrees
  (monorepo use). `GraphConfig.include_external` controls whether edges to
  stdlib/3rd-party modules appear in the graph.
- `models.py` — Domain models: `Chunk`, `GraphNode`, `GraphEdge`,
  `ImpactResult`, `NodeKind`, `EdgeKind`.
- `index_workspace.py` — `IndexWorkspace` and `ResolvedCheckout`: resolves
  `[[index.roots]]` entries to absolute paths, applies `include` scopes,
  and loads per-repo `.gitignore`. Used by the pipeline, watcher, and CLI.
- `errors.py` — Shared exception types (`IndexStaleError`, `ConfigError`).
- `lock.py` — Advisory file lock preventing concurrent index writes.
- `timing.py` — `timed_phase` context manager for wall-clock logging.
- `utils.py` — Content hashing, file reading, changed-file detection.
