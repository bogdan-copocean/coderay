# vcs

Git integration for file discovery and change detection.

`Git` in `git.py`:

- Discovers source files via `git ls-files` (respects `.gitignore` via
  `pathspec` — same files git tracks, nothing more).
- Computes diffs against the last indexed commit to find added/modified/
  deleted files for incremental builds.
- Tracks the current branch name per repo, persisted in index state.

Used exclusively by `pipeline/indexer.py` and `pipeline/watcher.py`.
