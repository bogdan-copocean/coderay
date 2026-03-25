# pipeline

Orchestrates index lifecycle: build, incremental update, and file watching.

## How it works

- `indexer.py` — `Indexer` discovers files via git, chunks them with
  tree-sitter, embeds with the configured provider, stores in LanceDB,
  and updates the graph and state. Supports full rebuild, incremental
  update, and resume from interruption (batched checkpoints).
- `watcher.py` — `FileWatcher` monitors the repo with watchdog, debounces
  rapid events, and runs `Indexer.update_incremental()` after changes.
  Respects `.gitignore` and detects branch switches.
