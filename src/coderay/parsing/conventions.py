"""Import and module resolution conventions aggregated from language configs."""

from __future__ import annotations

from coderay.parsing.languages import LANGUAGE_REGISTRY


def get_init_filenames() -> set[str]:
    """Return init-style filenames (e.g. __init__, index)."""
    names: set[str] = set()
    for cfg in LANGUAGE_REGISTRY.values():
        names.update(cfg.init_filenames)
    return names
