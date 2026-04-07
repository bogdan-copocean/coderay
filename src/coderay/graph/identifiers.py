"""Identifier and path utilities for graph."""

from __future__ import annotations

from coderay.parsing.conventions import get_init_filenames
from coderay.parsing.languages import get_supported_extensions

_KNOWN_EXTENSIONS: frozenset[str] = frozenset()
_KNOWN_INIT_FILENAMES: frozenset[str] = frozenset()


def _ensure_registry_cache() -> None:
    """Populate cached extension and init filename sets."""
    global _KNOWN_EXTENSIONS, _KNOWN_INIT_FILENAMES  # noqa: PLW0603
    if not _KNOWN_EXTENSIONS:
        _KNOWN_EXTENSIONS = frozenset(get_supported_extensions())
        _KNOWN_INIT_FILENAMES = frozenset(get_init_filenames())


def caller_id_for_scope(module_id: str, file_path: str, scope_stack: list[str]) -> str:
    """Return the graph node id for the current lexical scope."""
    if scope_stack:
        return f"{file_path}::{'.'.join(scope_stack)}"
    return module_id


def file_path_to_module_names(file_path: str) -> list[str]:
    """Derive possible module names from file path."""
    _ensure_registry_cache()

    cleaned = file_path
    for ext in sorted(_KNOWN_EXTENSIONS, key=len, reverse=True):
        if cleaned.endswith(ext):
            cleaned = cleaned[: -len(ext)]
            break

    parts = cleaned.replace("\\", "/").split("/")

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
