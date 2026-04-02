# pipeline

Orchestrates the index lifecycle: build, incremental update, and file watching.

## Files

- `indexer.py` — `Indexer` drives the full build and incremental update.
  Discovers files via git, chunks with tree-sitter, embeds, stores in
  LanceDB, and refreshes the graph. Writes batched checkpoints so an
  interrupted build can resume. Calls `maintain()` after every build.
- `watcher.py` — `FileWatcher` (watchdog) debounces filesystem events and
  calls `Indexer.update_incremental()`. Event filtering mirrors the indexing
  scope: `[[index.roots]]`, `exclude_patterns`, and per-repo `.gitignore`.

## Deindexing

`.coderay.toml` is the source of truth for scope. On every incremental update
the indexer reconciles desired files (current config) against indexed files
(`file_hashes.json`). Files that fall out of scope — deleted, matched by a
new `exclude_patterns` rule, or removed from an `include` list — are removed
from the vector store and graph automatically.

## Build modes

| Mode | When to use |
|------|-------------|
| `build` / `watch` | Normal — only changed files are re-indexed |
| `build --full` | After changing `[embedder]` model, backend, or dimensions |
