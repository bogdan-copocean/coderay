"""Index schema versioning.

Prevents stale/incompatible indexes from being silently used after
embedding model changes, schema upgrades, etc.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

INDEX_SCHEMA_VERSION = 2
VERSION_FILENAME = "version.json"


class IndexVersionError(Exception):
    """Raised when the index schema version doesn't match the current code."""


def write_index_version(index_dir: str | Path) -> None:
    """Write the current schema version to index_dir/version.json."""
    path = Path(index_dir) / VERSION_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": INDEX_SCHEMA_VERSION}))


def read_index_version(index_dir: str | Path) -> int | None:
    """Read the schema version from index_dir/version.json. Returns None if missing."""
    path = Path(index_dir) / VERSION_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return int(data.get("schema_version", 0))
    except Exception:
        return None


def check_index_version(index_dir: str | Path) -> None:
    """Warn if the index version doesn't match the current schema.

    Does not raise -- logs a warning so callers can decide how to handle it.
    """
    version = read_index_version(index_dir)
    if version is None:
        return
    if version != INDEX_SCHEMA_VERSION:
        logger.warning(
            "Index schema version mismatch: index=%s, code=%s. "
            "Consider rebuilding with 'index build --full'.",
            version,
            INDEX_SCHEMA_VERSION,
        )
