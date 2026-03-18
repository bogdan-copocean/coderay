"""Shared utilities for graph extraction."""

from coderay.parsing.languages import get_init_filenames

# Node types that contain base class names (Python: argument_list, superclass; JS/TS: extends_clause, class_heritage)
_BASE_CLASS_NODE_TYPES = ("argument_list", "superclass", "extends_clause", "class_heritage")


def is_init_file(file_path: str) -> bool:
    """Return True if file_path is package init (e.g. __init__.py)."""
    # Extract filename without path, then stem without extension
    name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem in get_init_filenames()


def resolve_relative_import(source_file: str, relative_target: str) -> str | None:
    """Resolve relative import to path; None if dots exceed depth.

    Supports Python (..foo.bar) and JS/TS (./foo/bar, ../utils/helper).
    """
    target = relative_target.replace("\\", "/")
    parts = source_file.replace("\\", "/").split("/")
    dir_parts = parts[:-1]

    # Python: ".foo", "..bar", "...baz" — dots then rest (no slash in prefix)
    # JS/TS: "./foo", "../bar", "../../a/b" — ./ or ../ then path
    if target.startswith("./"):
        target = target[2:]
        levels_up = 0
    elif target.startswith("../"):
        levels_up = 0
        while target.startswith("../"):
            levels_up += 1
            target = target[3:]
        target = target.lstrip("/")
    else:
        # Python-style: count leading dots
        dots = len(target) - len(target.lstrip("."))
        rest = target[dots:].lstrip("/")
        levels_up = max(dots - 1, 0)
        target = rest
        if target:
            target = target.replace(".", "/")

    if levels_up > len(dir_parts):
        return None
    if levels_up > 0:
        dir_parts = dir_parts[:-levels_up]

    if target:
        dir_parts.extend(target.split("/"))

    return "/".join(dir_parts) if dir_parts else None
