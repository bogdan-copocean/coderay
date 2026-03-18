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
    """Return path to lock file in index dir."""
    return Path(index_dir) / LOCK_FILENAME


@contextmanager
def acquire_indexer_lock(
    index_dir: str | Path,
    timeout: float = DEFAULT_TIMEOUT,
) -> Generator[FileLock, None, None]:
    """Acquire exclusive lock for index writes."""
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
