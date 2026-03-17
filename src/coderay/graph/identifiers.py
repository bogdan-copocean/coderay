"""Shared identifier and path utilities for the graph module."""

from __future__ import annotations

from coderay.parsing.languages import get_init_filenames, get_supported_extensions

_KNOWN_EXTENSIONS: frozenset[str] = frozenset()
_KNOWN_INIT_FILENAMES: frozenset[str] = frozenset()


def _ensure_registry_cache() -> None:
    """Lazily populate the cached extension and init filename sets."""
    global _KNOWN_EXTENSIONS, _KNOWN_INIT_FILENAMES  # noqa: PLW0603
    if not _KNOWN_EXTENSIONS:
        _KNOWN_EXTENSIONS = frozenset(get_supported_extensions())
        _KNOWN_INIT_FILENAMES = frozenset(get_init_filenames())


def file_path_to_module_names(file_path: str) -> list[str]:
    """Derive possible module names from a file path.

    Strips extension, common layout prefix (src), and init filenames,
    then produces dotted and slashed variants for each path suffix.

    Args:
        file_path: Path to a source file (e.g. ``src/pkg/mod.py``).

    Returns:
        List of possible module names (e.g. ``["pkg.mod", "pkg/mod", "mod"]``).
    """
    _ensure_registry_cache()

    cleaned = file_path
    for ext in sorted(_KNOWN_EXTENSIONS, key=len, reverse=True):
        if cleaned.endswith(ext):
            cleaned = cleaned[: -len(ext)]
            break

    parts = cleaned.replace("\\", "/").split("/")

    if parts and parts[0] == "src":
        parts = parts[1:]

    if parts and parts[-1] in _KNOWN_INIT_FILENAMES:
        parts = parts[:-1]

    if not parts:
        return []

    names: list[str] = []
    for i in range(len(parts)):
        suffix = parts[i:]
        dotted = ".".join(suffix)
        names.append(dotted)
        slashed = "/".join(suffix)
        if slashed != dotted:
            names.append(slashed)
    return names
