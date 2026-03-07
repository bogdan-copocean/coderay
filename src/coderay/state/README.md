# state

Manages index metadata persistence.

- `machine.py` — `StateMachine` tracks indexer run state
  (in_progress, done, errored, incomplete) in `meta.json` and file
  content hashes in `file_hashes.json`. Supports resume via checkpointed
  progress.
- `version.py` — Schema versioning (`version.json`). Warns on mismatch
  so stale indexes aren't silently used after upgrades.
