import hashlib
from pathlib import Path


def hash_content(content: str) -> str:
    """Compute SHA-256 hex digest of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def read_from_path(path: Path) -> str:
    """Read file as UTF-8 text with replacement for invalid bytes."""
    return path.read_text(encoding="utf-8", errors="replace")


def files_with_changed_content(
    repo: Path,
    paths: list[Path],
    file_hashes: dict[str, str],
) -> list[Path]:
    """Return paths whose content hash differs from file_hashes (repo-relative keys)."""
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
        except Exception:
            result.append(p)
    return result


def files_with_changed_content_keys(
    keyed_paths: list[tuple[str, Path]],
    file_hashes: dict[str, str],
) -> list[tuple[str, Path]]:
    """Return (logical_key, path) pairs whose hash differs from file_hashes."""
    result: list[tuple[str, Path]] = []
    for key, p in keyed_paths:
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            h = hash_content(content)
            if file_hashes.get(key) != h:
                result.append((key, p))
        except Exception:
            result.append((key, p))
    return result
