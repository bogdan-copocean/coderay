# state

Manages index metadata persistence across builds.

- `machine.py` — `StateMachine` tracks indexer run state
  (`in_progress`, `done`, `errored`, `incomplete`) in `meta.json` and
  file content hashes in `file_hashes.json`. Hashes enable change detection
  for incremental builds and support resume after interruption via batched
  checkpoints.
- `version.py` — Schema versioning (`version.json`). Raises on mismatch
  so stale indexes from old schema versions aren't silently used.
