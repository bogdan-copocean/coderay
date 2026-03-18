"""Shared utilities for graph extraction."""

from coderay.parsing.languages import get_init_filenames


def is_init_file(file_path: str) -> bool:
    """Return True if file_path is package init (e.g. __init__.py)."""
    # Extract filename without path, then stem without extension
    name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem in get_init_filenames()


def resolve_relative_import(source_file: str, relative_target: str) -> str | None:
    """Resolve relative import to path; None if dots exceed depth."""
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
