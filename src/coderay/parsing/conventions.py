"""Import and module resolution conventions aggregated from language configs."""

from __future__ import annotations

from coderay.parsing.languages import LANGUAGE_REGISTRY


def get_init_filenames() -> set[str]:
    """Return init-style filenames (e.g. __init__, index)."""
    names: set[str] = set()
    for cfg in LANGUAGE_REGISTRY.values():
        names.update(cfg.init_filenames)
    return names


def is_init_file(file_path: str) -> bool:
    """Return True if file_path is a package init file (e.g. __init__.py, index.ts)."""
    name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem in get_init_filenames()


def resolve_relative_import(source_file: str, relative_target: str) -> str | None:
    """Resolve a relative import path against its source file.

    Supports Python (``..foo.bar``) and JS/TS (``./foo``, ``../bar``).
    Returns None if the dot-levels exceed the source file's directory depth.
    """
    target = relative_target.replace("\\", "/")
    parts = source_file.replace("\\", "/").split("/")
    dir_parts = parts[:-1]

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
        target = rest.replace(".", "/") if rest else ""

    if levels_up > len(dir_parts):
        return None
    if levels_up > 0:
        dir_parts = dir_parts[:-levels_up]

    if target:
        dir_parts.extend(target.split("/"))

    return "/".join(dir_parts) if dir_parts else None
