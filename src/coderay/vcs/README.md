# vcs

Git integration for file discovery and change detection.

`Git` in `git.py` discovers source files via `git ls-files`, computes
diffs against the last indexed commit, and detects branch switches.
File filtering respects `.gitignore` via `pathspec`.
