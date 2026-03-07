"""
File lock for indexer build/update.

What is a file lock?
  A file lock is an advisory lock on a file (or empty lock file) so that only one
  process can hold it at a time. When process A acquires the lock, it creates/opens
  the lock file and holds an exclusive lock (e.g. via fcntl.flock on Unix). Process B
  trying to acquire the same lock will block until A releases it, or fail after a
  timeout. This prevents two indexer runs from writing to the same LanceDB index and
  meta.json at once, which would corrupt state or duplicate work.

How we use it:
  - Only build and update acquire the lock; search does not (read-only).
  - Lock is held for the full duration of the indexing run (discover -> chunk -> embed -> store).
  - Lock file lives in the index directory (e.g. .index/.indexer.lock) and is gitignored.
  - Uses the filelock package (cross-platform). If a second process tries to build/update
    while the first holds the lock, it blocks until release or timeout (default 300s).
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock

logger = logging.getLogger(__name__)

LOCK_FILENAME = ".indexer.lock"
DEFAULT_TIMEOUT = 300  # seconds to wait for lock before giving up


def lock_path(index_dir: str | Path) -> Path:
    """Path to the lock file inside the index directory."""
    return Path(index_dir) / LOCK_FILENAME


@contextmanager
def acquire_indexer_lock(
    index_dir: str | Path,
    timeout: float = DEFAULT_TIMEOUT,
) -> Generator[FileLock, None, None]:
    """
    Context manager that acquires the indexer lock before build/update.

    Yields the FileLock so the caller holds the lock for the duration of the with block.
    Release is automatic on exit. If the lock cannot be acquired within timeout
    seconds, Timeout is raised.
    """
    path = lock_path(index_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path), timeout=timeout)
    try:
        lock.acquire()
        logger.debug("Acquired indexer lock at %s", path)
        yield lock
    finally:
        lock.release()
        logger.debug("Released indexer lock at %s", path)
