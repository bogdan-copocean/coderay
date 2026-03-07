# core

Shared foundations used across all modules.

- `config.py` — YAML config loading with defaults + deep merge.
- `models.py` — Domain models: `Chunk`, `GraphNode`, `GraphEdge`, enums.
- `lock.py` — Advisory file lock preventing concurrent index writes.
- `timing.py` — `@timed` decorator and `timed_phase` context manager.
- `utils.py` — Content hashing, file reading, changed-file detection.
