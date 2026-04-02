from __future__ import annotations

import logging
import os
import re
from importlib import resources
from pathlib import Path
from typing import Annotated, Any, Literal

import tomllib
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from coderay.embedding.backend_resolve import resolved_embedder_backend

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when config is invalid or has unknown keys."""


_INDEX_ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def sanitize_index_root_alias_default(name: str) -> str:
    """Map a directory name to a valid index alias (letters, digits, -, _)."""
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", name)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "root"


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


class IndexRootEntry(BaseConfig):
    """One git checkout and optional subtree or file under it."""

    repo: str
    include: list[str] | None = None
    alias: str | None = None

    @field_validator("include", mode="before")
    @classmethod
    def _normalize_include(cls, v: Any) -> list[str] | None:
        """Accept a single path or a list; normalize to a list or None."""
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return None if not s else [s]
        if isinstance(v, list):
            out = [str(x).strip() for x in v if str(x).strip()]
            return out or None
        raise ValueError("include must be a string or list of strings")


class IndexConfig(BaseConfig):
    path: str
    roots: list[IndexRootEntry] = Field(default_factory=list)
    exclude_patterns: Annotated[list[str], "optional, besides .gitignore"]

    @staticmethod
    def _disambiguate_aliases(desired: list[str]) -> list[str]:
        """Make aliases unique; append -2, -3 on collision."""
        used: set[str] = set()
        out: list[str] = []
        for name in desired:
            candidate = name
            n = 2
            while candidate in used:
                candidate = f"{name}-{n}"
                n += 1
            used.add(candidate)
            out.append(candidate)
        return out

    @model_validator(mode="after")
    def _default_roots(self) -> IndexConfig:
        """Default single project checkout when roots unset."""
        if self.roots:
            return self
        return self.model_copy(
            update={"roots": [IndexRootEntry(repo=".", include=None)]}
        )

    @model_validator(mode="after")
    def _validate_roots_and_resolve_aliases(self, info: ValidationInfo) -> IndexConfig:
        """Enforce root invariants and assign unique aliases per checkout."""
        ctx = info.context
        project_root = ctx.get("project_root") if isinstance(ctx, dict) else None
        if project_root is None:
            return self
        project_root = Path(project_root).resolve()

        roots = self.roots
        if not roots:
            raise ConfigError("index.roots must list at least one checkout")

        explicit = [r.alias for r in roots if r.alias]
        if len(explicit) != len(set(explicit)):
            raise ConfigError("index.roots alias values must be unique")
        for r in roots:
            if r.alias is not None:
                a = r.alias.strip()
                if not a:
                    raise ConfigError("index.roots alias must not be empty")
                if not _INDEX_ALIAS_RE.fullmatch(a):
                    raise ConfigError(
                        "index.roots alias may only contain letters, digits, "
                        "hyphens, and underscores"
                    )

        dot_count = sum(1 for r in roots if r.repo.strip() == ".")
        if len(roots) > 1 and dot_count != 1:
            raise ConfigError(
                'When multiple index.roots are set, exactly one must use repo = "."'
            )
        if dot_count > 1:
            raise ConfigError('At most one index.roots row may use repo = "."')

        desired: list[str] = []
        for entry in roots:
            if entry.alias:
                desired.append(entry.alias.strip())
            else:
                raw = Path(entry.repo).expanduser()
                rr = (
                    (project_root / raw).resolve()
                    if not raw.is_absolute()
                    else raw.resolve()
                )
                desired.append(sanitize_index_root_alias_default(rr.name))

        final_names = IndexConfig._disambiguate_aliases(desired)
        new_roots = [
            IndexRootEntry(repo=e.repo, include=e.include, alias=name)
            for e, name in zip(roots, final_names, strict=True)
        ]
        return self.model_copy(update={"roots": new_roots})


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
    default_scope: Literal["primary", "*"] = "primary"


class WatcherConfig(BaseConfig):
    debounce: Annotated[int, "in seconds"]


class GraphConfig(BaseConfig):
    """Graph edge filtering."""

    include_external: Annotated[
        bool, "include edges targeting stdlib/3rd-party modules"
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
    """Load shipped default TOML as dict (with ``${INDEX_DIR}`` substituted)."""
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
    try:
        parsed = Config.model_validate(
            merged,
            context={"project_root": repo_root.resolve()},
        )
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
            f"Config not found at {cfg_path}. Run `coderay init` first where "
            ".coderay.toml lives."
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
