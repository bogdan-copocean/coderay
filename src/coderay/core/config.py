from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Annotated, Any

import yaml

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is invalid or contains unknown keys."""


DEFAULT_INDEX_DIR = ".index"
DEFAULT_CONFIG_FILENAME = "config.yaml"
ENV_INDEX_DIR = "CODERAY_INDEX_DIR"
ENV_CONFIG_FILE = "CODERAY_CONFIG_FILE"


@dataclass(frozen=True)
class EmbedderConfig:
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    dimensions: int = 384


@dataclass(frozen=True)
class IndexConfig:
    path: str = DEFAULT_INDEX_DIR
    exclude_patterns: Annotated[list[str], "optional, besides .gitignore"] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class BoostRule:
    path: str
    score: float


@dataclass(frozen=True)
class SemanticSearchConfig:
    boost_rules: BoostRule | None = None
    metric: str = "cosine"


@dataclass(frozen=True)
class WatcherConfig:
    debounce: Annotated[int, "in seconds"] = 2
    exclude_patterns: Annotated[str, "besides .gitignore"] | None = None
    branch_switch_threshold: int = 50


@dataclass(frozen=True)
class Config:
    embedder: EmbedderConfig = field(default_factory=EmbedderConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    semantic_search: SemanticSearchConfig = field(default_factory=SemanticSearchConfig)
    watcher: WatcherConfig = field(default_factory=WatcherConfig)


def _resolve_index_dir() -> Path:
    """Resolve the index directory from environment or default.

    Returns:
        Resolved index directory path.
    """
    env = os.environ.get(ENV_INDEX_DIR)
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / DEFAULT_INDEX_DIR).resolve()


def _resolve_config_path(index_dir: Path) -> Path:
    """Resolve the config file path under the index directory.

    Args:
        index_dir: Index directory to search in.

    Returns:
        Resolved config file path.
    """
    name = os.environ.get(ENV_CONFIG_FILE, DEFAULT_CONFIG_FILENAME)
    return index_dir / name


def load_config() -> Config:
    """Load the application configuration as a frozen dataclass.

    Returns:
        Loaded configuration with resolved index path.

    Raises:
        ConfigError: If the config file contains unknown keys or is invalid.
    """
    index_dir = _resolve_index_dir()

    cfg_path = _resolve_config_path(index_dir)
    if cfg_path.is_file():
        try:
            with cfg_path.open() as f:
                overrides = yaml.safe_load(f) or {}
            logger.info("Loaded config overrides from %s", cfg_path)
            return _deep_merge(overrides, index_dir=index_dir)
        except ConfigError:
            raise
        except Exception as e:
            logger.warning("Failed to load config from %s: %s", cfg_path, e)

    # No config file: return defaults with resolved index path
    default_data: dict[str, Any] = asdict(Config())
    index_dict = default_data.get("index", {}) or {}
    index_dict["path"] = str(index_dir)
    default_data["index"] = index_dict
    return Config(
        embedder=EmbedderConfig(**default_data.get("embedder", {})),
        index=IndexConfig(**default_data.get("index", {})),
        semantic_search=SemanticSearchConfig(
            **default_data.get("semantic_search", {})  # type: ignore[arg-type]
        ),
        watcher=WatcherConfig(**default_data.get("watcher", {})),
    )


def _deep_merge(overrides: dict, *, index_dir: Path) -> Config:
    """Apply validated overrides to the default configuration.

    Args:
        overrides: Raw overrides loaded from the YAML config file.
        index_dir: Resolved index directory to inject into the result.

    Returns:
        Config: New configuration instance with overrides applied.

    Raises:
        ConfigError: If overrides contain unknown top-level or nested keys.
    """
    base: dict[str, Any] = asdict(Config())

    # Validate unknown top-level keys.
    unknown_top = set(overrides.keys()) - set(base.keys())
    if unknown_top:
        raise ConfigError(f"Unknown top-level config keys: {sorted(unknown_top)}")

    merged: dict[str, Any] = {}
    for k, default_val in base.items():
        if k in overrides:
            override_val = overrides[k]
            if isinstance(default_val, dict) and isinstance(override_val, dict):
                # Validate unknown nested keys for this section.
                unknown_nested = set(override_val.keys()) - set(default_val.keys())
                if unknown_nested:
                    raise ConfigError(
                        f"Unknown config keys under '{k}': {sorted(unknown_nested)}"
                    )
                merged[k] = {**default_val, **override_val}
            else:
                merged[k] = override_val
        else:
            merged[k] = default_val

    # Ensure index.path reflects the resolved index_dir
    index_dict = merged.get("index", {}) or {}
    index_dict["path"] = str(index_dir)
    merged["index"] = index_dict

    return Config(
        embedder=EmbedderConfig(**merged.get("embedder", {})),
        index=IndexConfig(**merged.get("index", {})),
        semantic_search=SemanticSearchConfig(
            **merged.get("semantic_search", {})  # type: ignore[arg-type]
        ),
        watcher=WatcherConfig(**merged.get("watcher", {})),
    )
