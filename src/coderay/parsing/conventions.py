"""Import and module resolution conventions aggregated from language configs."""

from __future__ import annotations

from coderay.parsing.languages import LANGUAGE_REGISTRY


def get_init_filenames() -> set[str]:
    """Return init-style filenames (e.g. __init__, index)."""
    names: set[str] = set()
    for cfg in LANGUAGE_REGISTRY.values():
        names.update(cfg.init_filenames)
    return names


def get_resolution_suffixes() -> list[str]:
    """Return file suffixes for import resolution."""
    suffixes: list[str] = []
    seen: set[str] = set()
    for cfg in LANGUAGE_REGISTRY.values():
        for ext in cfg.extensions:
            if ext not in seen:
                suffixes.append(ext)
                seen.add(ext)
            for init in cfg.init_filenames:
                combo = f"/{init}{ext}"
                if combo not in seen:
                    suffixes.append(combo)
                    seen.add(combo)
    return suffixes
