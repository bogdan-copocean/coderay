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
    """Return paths whose content hash differs from file_hashes."""
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
