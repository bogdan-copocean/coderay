from __future__ import annotations

import logging
import os
from importlib import resources
from pathlib import Path
from typing import Annotated, Any

import tomllib
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from coderay.embedding.backend_resolve import resolved_embedder_backend

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when config is invalid or has unknown keys."""


DEFAULT_CONFIG_FILENAME = ".coderay.toml"
ENV_REPO_ROOT = "CODERAY_REPO_ROOT"


class BaseConfig(BaseModel):
    """Shared pydantic settings; reject unknown keys."""

    model_config = ConfigDict(extra="forbid")


class FastembedEmbedderConfig(BaseConfig):
    """ONNX / CPU path via fastembed."""

    model_name: str
    dimensions: int
    batch_size: int
    matryoshka_dimensions: int | None = None


class MLXEmbedderConfig(BaseConfig):
    """Apple Silicon path via mlx-embeddings (optional `pip install coderay[mlx]`)."""

    model_name: str
    dimensions: int
    batch_size: int
    matryoshka_dimensions: int | None = None


class EmbedderConfig(BaseConfig):
    """Embedding: pick backend; each backend has its own model and dimensions."""

    backend: str
    fastembed: FastembedEmbedderConfig
    mlx: MLXEmbedderConfig

    def effective_dimensions(self) -> int:
        """Return vector size for the resolved backend (auto picks MLX or fastembed)."""
        b = resolved_embedder_backend(self.backend)
        cfg = self.mlx if b == "mlx" else self.fastembed
        return cfg.matryoshka_dimensions or cfg.dimensions


class IndexConfig(BaseConfig):
    path: str
    paths: list[str]
    exclude_patterns: Annotated[list[str], "optional, besides .gitignore"]

    @model_validator(mode="before")
    @classmethod
    def _map_dir_to_path(cls, data):
        """Map TOML `index.dir` to runtime `index.path`."""
        if not isinstance(data, dict):
            return data
        if "path" in data and "dir" in data:
            raise ValueError("Use only one of 'index.path' or 'index.dir'")
        if "dir" in data:
            data = dict(data)
            data["path"] = data.pop("dir")
        return data


class BoostRule(BaseConfig):
    """Path-based score rule (regex + factor)."""

    pattern: str
    factor: float


class BoostingConfig(BaseConfig):
    """Path-based score rules."""

    penalties: list[BoostRule]
    bonuses: list[BoostRule]


class SemanticSearchConfig(BaseConfig):
    boosting: BoostingConfig
    metric: str
    hybrid: bool


class WatcherConfig(BaseConfig):
    debounce: Annotated[int, "in seconds"]
    exclude_patterns: Annotated[list[str], "besides .gitignore"]


class GraphConfig(BaseConfig):
    """Module filtering for graph (CALLS, IMPORTS edges)."""

    exclude_modules: Annotated[
        list[str], "module names/prefixes to exclude from graph edges"
    ]
    include_modules: Annotated[
        list[str], "module names to force-include (override excludes)"
    ]


class Config(BaseConfig):
    embedder: EmbedderConfig
    index: IndexConfig
    search: SemanticSearchConfig
    watcher: WatcherConfig
    graph: GraphConfig


class ProjectNotInitializedError(RuntimeError):
    """Raised when `.coderay.toml` is missing."""


_config_cache: dict[Path, Config] = {}


def _config_path(repo_root: Path) -> Path:
    """Return `.coderay.toml` path under repo_root."""
    return repo_root / DEFAULT_CONFIG_FILENAME


def _read_default_toml_dict(repo_root: Path) -> dict[str, Any]:
    """Load shipped default TOML as dict (with `index.dir` resolved)."""
    tmpl = (
        resources.files("coderay.core.defaults")
        .joinpath("default.coderay.toml")
        .read_text(encoding="utf-8")
    )
    index_dir = (repo_root.resolve() / ".coderay").as_posix()
    raw = tomllib.loads(tmpl.replace("${INDEX_DIR}", index_dir))
    if not isinstance(raw, dict):
        raise ConfigError("Default config must be a TOML table")
    return raw


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge TOML tables; overrides win; recurse into dicts."""
    out: dict[str, Any] = dict(defaults)
    for k, v in overrides.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _coalesce_index_dir_path(idx: dict[str, Any]) -> dict[str, Any]:
    """Map `dir` to `path` after merge so both keys never appear."""
    idx = dict(idx)
    if "dir" in idx:
        idx["path"] = idx.pop("dir")
    return idx


def _resolve_index_paths(repo_root: Path, parsed: Config) -> Config:
    """Resolve relative index.path against repo_root."""
    idx_dir = Path(parsed.index.path).expanduser()
    index_dir = (
        (repo_root / idx_dir).resolve()
        if not idx_dir.is_absolute()
        else idx_dir.resolve()
    )
    return parsed.model_copy(
        update={
            "index": parsed.index.model_copy(update={"path": str(index_dir)}),
        },
        deep=True,
    )


def config_for_repo(repo_root: Path, overrides: dict[str, Any] | None = None) -> Config:
    """Build config from shipped defaults and optional overrides (tests, tooling)."""
    base = _read_default_toml_dict(repo_root)
    merged = _deep_merge(base, overrides) if overrides else base
    if "index" in merged and isinstance(merged["index"], dict):
        merged = dict(merged)
        merged["index"] = _coalesce_index_dir_path(merged["index"])
    try:
        parsed = Config.model_validate(merged)
    except ValidationError as e:
        raise ConfigError(f"Invalid config: {e}") from e
    return _resolve_index_paths(repo_root, parsed)


def get_config(repo_root: Path | None = None) -> Config:
    """Return application config for repo_root (cached per process)."""
    if repo_root is None:
        env = os.environ.get(ENV_REPO_ROOT)
        repo_root = Path(env).expanduser() if env else Path.cwd()
    root = repo_root.resolve()
    cached = _config_cache.get(root)
    if cached is not None:
        return cached
    cfg = load_config(root)
    _config_cache[root] = cfg
    return cfg


def _reset_config_for_testing(config: Config | None = None) -> None:
    """Reset config cache; for tests only."""
    _config_cache.clear()
    if config is not None:
        _config_cache[Path.cwd().resolve()] = config


def load_config(repo_root: Path) -> Config:
    """Load config from `<repo_root>/.coderay.toml` merged with shipped defaults."""
    repo_root = repo_root.resolve()
    cfg_path = _config_path(repo_root)
    if not cfg_path.is_file():
        raise ProjectNotInitializedError(
            f"Config not found at {cfg_path}. Run `coderay init --repo {repo_root}`."
        )

    user = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(user, dict):
        raise ConfigError("Config must be a TOML table")
    return config_for_repo(repo_root, user)


def render_default_toml(repo_root: Path) -> str:
    """Render default `.coderay.toml` contents."""
    tmpl = (
        resources.files("coderay.core.defaults")
        .joinpath("default.coderay.toml")
        .read_text(encoding="utf-8")
    )
    index_dir = (repo_root.resolve() / ".coderay").as_posix()
    return tmpl.replace("${INDEX_DIR}", index_dir)
