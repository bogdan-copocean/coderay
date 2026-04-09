"""Graph-level utilities (module name derivation)."""

from __future__ import annotations

from coderay.parsing.conventions import get_init_filenames
from coderay.parsing.languages import get_supported_extensions

_KNOWN_EXTENSIONS: frozenset[str] = frozenset()
_KNOWN_INIT_FILENAMES: frozenset[str] = frozenset()


def _ensure_registry_cache() -> None:
    global _KNOWN_EXTENSIONS, _KNOWN_INIT_FILENAMES  # noqa: PLW0603
    if not _KNOWN_EXTENSIONS:
        _KNOWN_EXTENSIONS = frozenset(get_supported_extensions())
        _KNOWN_INIT_FILENAMES = frozenset(get_init_filenames())


def file_path_to_module_names(file_path: str) -> list[str]:
    """Derive candidate module names from a file path.

    e.g. "src/foo/bar.py" -> ["foo.bar", "bar", "foo/bar", ...]
    """
    _ensure_registry_cache()

    cleaned = file_path
    for ext in sorted(_KNOWN_EXTENSIONS, key=len, reverse=True):
        if cleaned.endswith(ext):
            cleaned = cleaned[: -len(ext)]
            break

    parts = cleaned.replace("\\", "/").split("/")

    # __init__ files represent the package, not a submodule.
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
