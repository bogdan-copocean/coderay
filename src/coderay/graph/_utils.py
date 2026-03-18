"""Shared utilities for graph extraction.

Used by FileContext and handler mixins. Keeps import/package logic
out of the main extractor and handlers.
"""

from coderay.parsing.languages import get_init_filenames


def is_init_file(file_path: str) -> bool:
    """Return True if *file_path* is a package init file (e.g. ``__init__.py``).

    Used when resolving imports: symbols from __init__.py are kept as
    mod::symbol (external-style) to avoid wrong edges when the symbol
    lives in a sub-module.
    """
    # Extract filename without path, then stem without extension
    name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem in get_init_filenames()


def resolve_relative_import(source_file: str, relative_target: str) -> str | None:
    """Resolve a Python relative import to a path-based target.

    Args:
        source_file: Path of the file containing the import.
        relative_target: Dotted import string starting with one or more dots.

    Returns:
        Slash-separated path (no extension), or None if dots exceed
        the directory depth.
    """
    # Count leading dots: "." = current pkg, ".." = parent, etc.
    dots = len(relative_target) - len(relative_target.lstrip("."))
    rest = relative_target[dots:]  # e.g. "..foo.bar" -> rest = "foo.bar"

    # Start from the directory containing source_file
    parts = source_file.replace("\\", "/").split("/")
    dir_parts = parts[:-1]

    # Walk up: "." means stay, ".." means one level up, "..." means two up
    levels_up = max(dots - 1, 0)
    if levels_up > len(dir_parts):
        return None
    if levels_up > 0:
        dir_parts = dir_parts[:-levels_up]

    # Append the relative module path (e.g. "foo.bar" -> ["foo", "bar"])
    if rest:
        dir_parts.extend(rest.split("."))

    return "/".join(dir_parts) if dir_parts else None
