from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Annotated, Any

import yaml

from coderay.embedding.backend_resolve import resolved_embedder_backend

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when config is invalid or has unknown keys."""


DEFAULT_INDEX_DIR = ".index"
DEFAULT_CONFIG_FILENAME = "config.yaml"
ENV_INDEX_DIR = "CODERAY_INDEX_DIR"
ENV_CONFIG_FILE = "CODERAY_CONFIG_FILE"


@dataclass(frozen=True)
class FastembedEmbedderConfig:
    """ONNX / CPU path via fastembed."""

    model_name: str = "BAAI/bge-small-en-v1.5"
    dimensions: int = 384
    matryoshka_dimensions: int | None = None


@dataclass(frozen=True)
class MLXEmbedderConfig:
    """Apple Silicon path via mlx-embeddings."""

    model_name: str = "mlx-community/bge-small-en-v1.5-bf16"
    dimensions: int = 384
    matryoshka_dimensions: int | None = None


@dataclass(frozen=True)
class EmbedderConfig:
    """Embedding: pick backend; each backend has its own model and dimensions."""

    backend: str = "auto"
    fastembed: FastembedEmbedderConfig = field(default_factory=FastembedEmbedderConfig)
    mlx: MLXEmbedderConfig = field(default_factory=MLXEmbedderConfig)

    def effective_dimensions(self) -> int:
        """Return vector size for the resolved backend (auto picks MLX or fastembed)."""
        b = resolved_embedder_backend(self.backend)
        return self.mlx.dimensions if b == "mlx" else self.fastembed.dimensions


@dataclass(frozen=True)
class IndexConfig:
    path: str = DEFAULT_INDEX_DIR
    exclude_patterns: Annotated[list[str], "optional, besides .gitignore"] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class BoostRule:
    """Path-based score rule (regex + factor)."""

    pattern: str
    factor: float


def _default_penalties() -> list[BoostRule]:
    """Return default penalty rules."""
    return [
        BoostRule(pattern=r"(^|/)tests?/", factor=0.5),
        BoostRule(pattern=r"(^|/)test_[^/]+\.py$", factor=0.5),
        BoostRule(pattern=r"(^|/)(mock|fixture|conftest)", factor=0.4),
    ]


def _default_bonuses() -> list[BoostRule]:
    """Return default bonus rules."""
    return [
        BoostRule(pattern=r"(^|/)src/", factor=1.1),
    ]


@dataclass(frozen=True)
class BoostingConfig:
    """Path-based score rules."""

    penalties: list[BoostRule] = field(default_factory=_default_penalties)
    bonuses: list[BoostRule] = field(default_factory=_default_bonuses)


def _default_boosting() -> BoostingConfig:
    """Return default boosting config."""
    return BoostingConfig(
        penalties=_default_penalties(),
        bonuses=_default_bonuses(),
    )


@dataclass(frozen=True)
class SemanticSearchConfig:
    boosting: BoostingConfig = field(default_factory=_default_boosting)
    metric: str = "cosine"
    hybrid: bool = True


@dataclass(frozen=True)
class WatcherConfig:
    debounce: Annotated[int, "in seconds"] = 2
    exclude_patterns: Annotated[str, "besides .gitignore"] | None = None


@dataclass(frozen=True)
class GraphConfig:
    """Module filtering for graph (CALLS, IMPORTS edges)."""

    exclude_modules: Annotated[
        list[str], "module names/prefixes to exclude from graph edges"
    ] = field(default_factory=list)
    include_modules: Annotated[
        list[str], "module names to force-include (override excludes)"
    ] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    embedder: EmbedderConfig = field(default_factory=EmbedderConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    semantic_search: SemanticSearchConfig = field(default_factory=SemanticSearchConfig)
    watcher: WatcherConfig = field(default_factory=WatcherConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)


def _parse_boosting(data: dict[str, Any]) -> BoostingConfig:
    """Parse dict into BoostingConfig."""
    raw_penalties = data.get("penalties")
    raw_bonuses = data.get("bonuses")
    penalties = (
        [BoostRule(**p) for p in raw_penalties]
        if raw_penalties
        else _default_penalties()
    )
    bonuses = (
        [BoostRule(**b) for b in raw_bonuses] if raw_bonuses else _default_bonuses()
    )
    return BoostingConfig(penalties=penalties, bonuses=bonuses)


def _parse_embedder_config(data: dict[str, Any]) -> EmbedderConfig:
    """Build EmbedderConfig from merged or YAML dict."""
    d = data or {}
    return EmbedderConfig(
        backend=str(d.get("backend", "auto")),
        fastembed=FastembedEmbedderConfig(**(d.get("fastembed") or {})),
        mlx=MLXEmbedderConfig(**(d.get("mlx") or {})),
    )


def _parse_semantic_search(data: dict[str, Any]) -> SemanticSearchConfig:
    """Parse dict into SemanticSearchConfig."""
    boosting_data = data.get("boosting") or {}
    return SemanticSearchConfig(
        boosting=_parse_boosting(boosting_data),
        metric=data.get("metric", "cosine"),
        hybrid=data.get("hybrid", True),
    )


def _resolve_index_dir() -> Path:
    """Resolve index directory from env or default."""
    env = os.environ.get(ENV_INDEX_DIR)
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / DEFAULT_INDEX_DIR).resolve()


def _resolve_config_path(index_dir: Path) -> Path:
    """Resolve config file path under index directory."""
    name = os.environ.get(ENV_CONFIG_FILE, DEFAULT_CONFIG_FILENAME)
    return index_dir / name


_config_cache: Config | None = None


def get_config() -> Config:
    """Return application config (cached per process)."""
    global _config_cache
    if _config_cache is None:
        _config_cache = _load_config_impl()
    return _config_cache


def _reset_config_for_testing(config: Config | None = None) -> None:
    """Reset config cache; for tests only."""
    global _config_cache
    _config_cache = config


def _load_config_impl() -> Config:
    """Load config from env and optional file; internal only."""
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
        embedder=_parse_embedder_config(default_data.get("embedder") or {}),
        index=IndexConfig(**default_data.get("index", {})),
        semantic_search=_parse_semantic_search(
            default_data.get("semantic_search", {}) or {}
        ),
        watcher=WatcherConfig(**default_data.get("watcher", {})),
        graph=GraphConfig(**default_data.get("graph", {})),
    )


def _deep_merge(overrides: dict, *, index_dir: Path) -> Config:
    """Apply validated overrides to default config."""
    base: dict[str, Any] = asdict(Config())

    def _merge_section(
        default_val: Any,
        override_val: Any,
        path: str,
    ) -> Any:
        """Merge config section; validate unknown keys."""
        if not isinstance(default_val, dict) or not isinstance(override_val, dict):
            return override_val

        unknown = set(override_val.keys()) - set(default_val.keys())
        if unknown:
            location = path or "."
            raise ConfigError(
                f"Unknown config keys under '{location}': {sorted(unknown)}"
            )

        merged_section: dict[str, Any] = {}
        for key, default_child in default_val.items():
            if key in override_val:
                value = override_val[key]
                if type(default_child) is not type(value):
                    raise ConfigError(
                        "config type mismatch under "
                        f"'{path or key}': {type(default_child)} is not {type(value)}"
                    )

                child_path = f"{path}.{key}" if path else key
                merged_section[key] = _merge_section(
                    default_child,
                    value,
                    child_path,
                )
            else:
                merged_section[key] = default_child
        return merged_section

    unknown_top = set(overrides.keys()) - set(base.keys())
    if unknown_top:
        raise ConfigError(f"Unknown top-level config keys: {sorted(unknown_top)}")

    merged: dict[str, Any] = {}
    for key, default_val in base.items():
        if key in overrides:
            override_val = overrides[key]
            if isinstance(default_val, dict) and isinstance(override_val, dict):
                merged[key] = _merge_section(default_val, override_val, key)
            else:
                if type(default_val) is not type(override_val):
                    raise ConfigError(
                        "config type mismatch under "
                        f"'{key}': {type(default_val)} is not {type(override_val)}"
                    )
                merged[key] = override_val
        else:
            merged[key] = default_val

    # Ensure index.path reflects the resolved index_dir
    index_dict = merged.get("index", {}) or {}
    index_dict["path"] = str(index_dir)
    merged["index"] = index_dict

    return Config(
        embedder=_parse_embedder_config(merged.get("embedder") or {}),
        index=IndexConfig(**merged.get("index", {})),
        semantic_search=_parse_semantic_search(merged.get("semantic_search", {}) or {}),
        watcher=WatcherConfig(**merged.get("watcher", {})),
        graph=GraphConfig(**merged.get("graph", {})),
    )
