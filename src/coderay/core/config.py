from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_DIMENSIONS = 384

DEFAULT_CONFIG: dict[str, Any] = {
    "embedder": {
        "provider": "local",
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "dimensions": DEFAULT_EMBEDDING_DIMENSIONS,
    },
    "index": {
        "path": ".index",
        "default_top_k": 10,
        "exclude_patterns": [],  # besides .gitignore
    },
    "search": {
        "boost_rules": {},
    },
    "graph": {
        "exclude_callees": [],
        "include_callees": [],
    },
    "watch": {
        "debounce_seconds": 2,
        "branch_switch_threshold": 50,
        "exclude_patterns": [],
    },
}


def get_embedding_dimensions(config: dict[str, Any]) -> int:
    """Return embedding dimension from config. Uses default if missing."""
    return int(
        (config.get("embedder") or {}).get("dimensions") or DEFAULT_EMBEDDING_DIMENSIONS
    )


def find_config(index_dir: Path) -> Path | None:
    """Return path to config.yaml if it exists under index_dir."""
    cfg = index_dir / "config.yaml"
    return cfg if cfg.is_file() else None


def load_config(index_dir: str | Path | None = None) -> dict[str, Any]:
    """Load config by merging defaults with optional config.yaml."""
    base = Path(index_dir or Path.cwd() / ".index")
    config = dict(DEFAULT_CONFIG)
    cfg_path = find_config(base)
    if cfg_path:
        try:
            with open(cfg_path) as f:
                overrides = yaml.safe_load(f) or {}
            _deep_merge(config, overrides)
        except Exception as e:
            logger.warning("Failed to load config from %s: %s", cfg_path, e)
    return config


def _deep_merge(base: dict, overrides: dict) -> None:
    """Merge overrides into base in-place (only one level deep for our use)."""
    for k, v in overrides.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
