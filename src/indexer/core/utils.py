"""Shared utilities: content hashing, file read, and changed-file filtering."""

import hashlib
from pathlib import Path


def hash_content(content: str) -> str:
    """
    Compute SHA-256 hash of file content (utf-8).

    Used to skip re-embedding unchanged files during incremental update.

    Args:
        content: Raw file content string.

    Returns:
        Hex digest of the content hash.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def read_from_path(path: Path) -> str:
    """
    Read file content as UTF-8 text.

    Args:
        path: Path to the file.

    Returns:
        File content. Invalid UTF-8 is replaced.
    """
    return path.read_text(encoding="utf-8", errors="replace")


def files_with_changed_content(
    repo: Path,
    paths: list[Path],
    file_hashes: dict[str, str],
) -> list[Path]:
    """
    Return paths whose content hash differs from file_hashes, or that are new.

    Used to skip re-embedding unchanged files during incremental update.

    Args:
        repo: Repository root (for relative path keys).
        paths: Absolute paths to candidate files.
        file_hashes: Mapping of relative path -> content hash from last run.

    Returns:
        Paths that are new or have a different hash.
    """
    result: list[Path] = []
    for p in paths:
        try:
            rel = str(p.relative_to(repo))
        except ValueError:
            result.append(p)
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            h = hash_content(content)
            if file_hashes.get(rel) != h:
                result.append(p)
        except Exception as e:
            result.append(p)
    return result
