"""Resolve index roots from config into a single workspace model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pathspec

from coderay.core.config import Config, ConfigError
from coderay.vcs.git import load_gitignore


@dataclass(frozen=True)
class ResolvedCheckout:
    """One configured git checkout and optional path scopes (union)."""

    alias: str
    repo_root: Path
    scopes: tuple[Path, ...] | None
    is_primary_checkout: bool
    gitignore_spec: pathspec.PathSpec

    def contains_path(self, abs_path: Path) -> bool:
        """Return True if abs_path is under repo and within at least one scope."""
        try:
            abs_path = abs_path.resolve()
            repo = self.repo_root.resolve()
            abs_path.relative_to(repo)
        except ValueError:
            return False
        if self.scopes is None:
            return True
        for sc in self.scopes:
            sc = sc.resolve()
            if sc.is_file():
                if abs_path == sc:
                    return True
                continue
            try:
                abs_path.relative_to(sc)
                return True
            except ValueError:
                continue
        return False

    def rel_key(self, abs_path: Path) -> str:
        """Path relative to repo as posix string."""
        return abs_path.resolve().relative_to(self.repo_root.resolve()).as_posix()


@dataclass(frozen=True)
class IndexWorkspace:
    """Resolved multi-root index scope; config_repo_root holds .coderay.toml."""

    config_repo_root: Path
    roots: tuple[ResolvedCheckout, ...]
    index_dir: Path
    index_exclude: pathspec.PathSpec

    @property
    def primary_alias(self) -> str:
        """Alias of the checkout with repo=`.'`, or first root."""
        for r in self.roots:
            if r.is_primary_checkout:
                return r.alias
        return self.roots[0].alias if self.roots else ""

    def by_alias(self) -> dict[str, ResolvedCheckout]:
        """Map alias -> checkout."""
        return {r.alias: r for r in self.roots}

    def logical_key(self, checkout: ResolvedCheckout, abs_path: Path) -> str:
        """Stable chunk path key for storage and graph."""
        return f"{checkout.alias}/{checkout.rel_key(abs_path)}"

    def logical_key_for_abs(self, abs_path: Path) -> str | None:
        """Return logical key if path is in scope for some checkout; else None."""
        abs_path = abs_path.resolve()
        for r in self.roots:
            if r.contains_path(abs_path):
                return self.logical_key(r, abs_path)
        return None

    def resolve_logical(self, logical: str) -> Path:
        """Map logical key to absolute path."""
        if "/" not in logical:
            raise ValueError(f"invalid logical path: {logical}")
        aid, rel = logical.split("/", 1)
        by = self.by_alias()
        if aid not in by:
            raise KeyError(aid)
        return by[aid].repo_root / rel

    def watch_directories(self) -> list[Path]:
        """Directories to attach filesystem watchers (per checkout or each scope)."""
        out: list[Path] = []
        for r in self.roots:
            if r.scopes is None:
                out.append(r.repo_root.resolve())
            else:
                out.extend(sc.resolve() for sc in r.scopes)
        return out


def resolve_index_workspace(config_repo_root: Path, config: Config) -> IndexWorkspace:
    """Build IndexWorkspace from merged config."""
    config_repo_root = config_repo_root.resolve()
    index_dir = Path(config.index.path).resolve()
    index_exclude = pathspec.PathSpec.from_lines(
        "gitignore", config.index.exclude_patterns or []
    )
    entries = config.index.roots
    roots: list[ResolvedCheckout] = []
    for entry in entries:
        alias = entry.alias
        if not alias:
            raise ConfigError(
                "index.roots entries must have resolved alias; "
                "load config with project_root validation context"
            )
        raw = Path(entry.repo).expanduser()
        repo_root = (
            (config_repo_root / raw).resolve()
            if not raw.is_absolute()
            else raw.resolve()
        )
        is_primary = entry.repo.strip() == "."
        scopes: tuple[Path, ...] | None = None
        if entry.include:
            resolved: list[Path] = []
            for raw in entry.include:  # type: ignore[assignment]
                inc = Path(raw)
                if inc.is_absolute():
                    p = inc.resolve()
                else:
                    p = (repo_root / inc).resolve()
                try:
                    p.relative_to(repo_root)
                except ValueError as e:
                    raise ValueError(
                        f"index.roots include {raw!r} escapes repo {repo_root}"
                    ) from e
                resolved.append(p)
            scopes = tuple(resolved)
        roots.append(
            ResolvedCheckout(
                alias=alias,
                repo_root=repo_root,
                scopes=scopes,
                is_primary_checkout=is_primary,
                gitignore_spec=load_gitignore(repo_root),
            )
        )

    return IndexWorkspace(
        config_repo_root=config_repo_root,
        roots=tuple(roots),
        index_dir=index_dir,
        index_exclude=index_exclude,
    )


def should_index_event(
    workspace: IndexWorkspace,
    abs_path: Path,
) -> tuple[str | None, str | None]:
    """If path is indexable, return (logical_key, rel_to_repo); else (None, None)."""
    abs_path = abs_path.resolve()
    index_dir = workspace.index_dir.resolve()
    try:
        abs_path.relative_to(index_dir)
        return None, None
    except ValueError:
        pass

    parts = abs_path.parts
    if ".git" in parts:
        return None, None

    for r in workspace.roots:
        if not r.contains_path(abs_path):
            continue
        rel = r.rel_key(abs_path)
        if r.gitignore_spec.match_file(rel):
            return None, None
        if workspace.index_exclude.match_file(rel):
            return None, None
        logical = workspace.logical_key(r, abs_path)
        return logical, rel
    return None, None
