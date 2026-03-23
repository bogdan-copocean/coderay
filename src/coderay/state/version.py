from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

INDEX_SCHEMA_VERSION = 3
VERSION_FILENAME = "version.json"


class IndexVersionError(Exception):
    """Raised when index schema version mismatches."""


def write_index_version(index_dir: str | Path) -> None:
    """Write schema version to version.json."""
    path = Path(index_dir) / VERSION_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": INDEX_SCHEMA_VERSION}))


def read_index_version(index_dir: str | Path) -> int | None:
    """Read schema version; None if missing."""
    path = Path(index_dir) / VERSION_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return int(data.get("schema_version", 0))
    except Exception:
        return None


def check_index_version(index_dir: str | Path) -> None:
    """Warn if index version mismatches schema."""
    version = read_index_version(index_dir)
    if version is None:
        return
    if version != INDEX_SCHEMA_VERSION:
        logger.warning(
            "Index schema version mismatch: index=%s, code=%s. "
            "Consider rebuilding with 'coderay build --full'.",
            version,
            INDEX_SCHEMA_VERSION,
        )
