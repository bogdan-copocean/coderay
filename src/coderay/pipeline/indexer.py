from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pathspec

from coderay.chunking.chunker import chunk_file
from coderay.core.config import ENV_REPO_ROOT, Config, get_config
from coderay.core.timing import timed, timed_phase
from coderay.core.utils import files_with_changed_content, hash_content, read_from_path
from coderay.embedding.base import Embedder, EmbedTask, load_embedder_from_config
from coderay.embedding.format import format_chunk_for_embedding
from coderay.graph.builder import build_and_save_graph
from coderay.state.machine import IndexMeta, MetaState, StateMachine
from coderay.state.version import check_index_version, write_index_version
from coderay.storage.lancedb import Store, index_exists
from coderay.vcs.git import Git

logger = logging.getLogger(__name__)

RESUME_BATCH_SIZE = 200
DEFAULT_REPO_ROOT = "."


@dataclass
class IndexResult:
    """Index build result: cached, updated, removed counts."""

    cached: int = 0
    updated: int = 0
    removed: int = 0

    def __str__(self) -> str:
        return (
            f"Cached: {self.cached}, Updated: {self.updated},"
            f" Removed: {self.removed} chunks"
        )


class Indexer:
    """Build and maintain semantic index."""

    def __init__(
        self,
        repo_root: str | Path = DEFAULT_REPO_ROOT,
        embedder: Embedder | None = None,
    ) -> None:
        """Initialize indexer."""
        self._repo_root = Path(repo_root).resolve()
        os.environ[ENV_REPO_ROOT] = str(self._repo_root)
        self._config = get_config(self._repo_root)
        self._index_dir = Path(self._config.index.path)
        self._include_roots = self._resolve_include_roots()
        self._git = Git(self._repo_root)
        self._state = StateMachine()
        self._embedder = embedder or load_embedder_from_config()
        self._store = Store()
        self._exclude_spec = pathspec.PathSpec.from_lines(
            "gitignore", self._config.index.exclude_patterns
        )
        check_index_version(self._index_dir)

    def _resolve_include_roots(self) -> list[Path]:
        """Resolve `index.paths` into absolute roots."""
        roots: list[Path] = []
        for raw in self._config.index.paths or []:
            p = Path(raw).expanduser()
            roots.append(
                (self._repo_root / p).resolve() if not p.is_absolute() else p.resolve()
            )
        return roots

    def _is_in_scope(self, path: Path) -> bool:
        """Return True if path is within configured include roots."""
        if not self._include_roots:
            return True
        p = path.resolve()
        for root in self._include_roots:
            try:
                p.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    @property
    def config(self) -> Config:
        """Return current config."""
        return self._config

    @property
    def repo_root(self) -> Path:
        """Return repo root."""
        return self._repo_root

    @property
    def index_dir(self) -> Path:
        """Return index dir."""
        return self._index_dir

    @property
    def current_state(self) -> IndexMeta | None:
        """Return current meta state; None if no run completed."""
        return self._state.current_state

    def _filter_excluded(self, paths: list[Path]) -> list[Path]:
        """Remove paths matching index.exclude_patterns."""
        return [
            p
            for p in paths
            if not self._exclude_spec.match_file(str(p.relative_to(self._repo_root)))
        ]

    @timed("full_build")
    def build_full(self) -> IndexResult:
        """Full rebuild: discover, chunk, embed, store."""

        current = self._state.current_state
        current_run = current.current_run if current else None
        saved_paths = current_run.paths_to_process if current_run else []
        processed_count = current_run.processed_count if current_run else 0

        can_resume = self._state.is_in_progress and self._state.has_partial_progress

        if can_resume:
            paths_remaining = saved_paths[processed_count:]
            if not paths_remaining:
                logger.info("Finishing full index build (checkpoint already complete)")
                self._state.finish(
                    last_commit=self._git.get_head_commit(),
                    branch=self._git.get_current_branch(),
                )
                write_index_version(self._index_dir)
                self._refresh_graph()
                return IndexResult(cached=len(self._state.file_hashes))
            logger.info(
                "Resuming full index build (%d file(s) remaining, %d / %d processed)",
                len(paths_remaining),
                processed_count,
                len(saved_paths),
            )
            paths_to_process = paths_remaining
            rel_paths = saved_paths
        else:
            self._state.set_incomplete()
            self._store.clear()

            py_files = self._filter_excluded(self._git.discover_files())
            if self._include_roots:
                py_files = [p for p in py_files if self._is_in_scope(p)]
            if not py_files:
                logger.warning("No source files found under %s", self._repo_root)
                return IndexResult(cached=len(self._state.file_hashes))

            rel_paths = [str(p.relative_to(self._repo_root)) for p in py_files]
            paths_to_process = rel_paths
            processed_count = 0
            self._state.start(
                branch=self._git.get_current_branch(),
                last_commit=self._git.get_head_commit(),
            )

        all_path_hashes, all_files_content = self._run_batch_loop(
            rel_paths=paths_to_process,
            full_rel_paths=rel_paths,
        )

        if can_resume:
            existing = self._state.file_hashes.copy()
            existing.update(all_path_hashes)
            self._state.file_hashes = existing
        else:
            self._state.file_hashes = all_path_hashes

        self._state.finish(
            last_commit=self._git.get_head_commit(),
            branch=self._git.get_current_branch(),
        )
        write_index_version(self._index_dir)
        self._refresh_graph(files_content=all_files_content)
        return IndexResult(updated=len(self._state.file_hashes))

    def update_incremental(self) -> IndexResult:
        """Incremental update: re-index changed/added/deleted files."""

        self._state.set_incomplete()

        current = self._state.current_state
        to_add, to_remove = self._git.get_files_to_index(
            last_commit=current.last_commit if current else None
        )
        to_add = self._filter_excluded(to_add)
        if self._include_roots:
            to_add = [p for p in to_add if self._is_in_scope(p)]
            to_remove = [
                p
                for p in to_remove
                if self._is_in_scope((self._repo_root / p).resolve())
            ]
        if to_remove:
            self._store.delete_by_paths(paths=to_remove)

        # Remove deleted hashes from state
        file_hashes = self._state.file_hashes.copy()
        for path in to_remove:
            file_hashes.pop(path, None)
        # Idempotent if to_remove is empty
        self._state.file_hashes = file_hashes

        # Check what files are changed
        changed_files = files_with_changed_content(
            repo=self._repo_root, paths=to_add, file_hashes=file_hashes
        )

        if not changed_files and not to_remove:
            self._state.finish(
                last_commit=self._git.get_head_commit(),
                branch=self._git.get_current_branch(),
            )
            self._refresh_graph()
            logger.info("Nothing to update")
            return IndexResult(cached=len(self._state.file_hashes))

        return self._update(
            paths_to_add=changed_files,
            file_hashes=file_hashes,
        )

    def _run_batch_loop(
        self,
        rel_paths: list[str],
        full_rel_paths: list[str],
    ) -> tuple[dict[str, str], list[tuple[str, str]]]:
        """Run pipeline in batches; save progress for resume."""
        all_path_hashes: dict[str, str] = {}
        all_files_content: list[tuple[str, str]] = []

        for i in range(0, len(rel_paths), RESUME_BATCH_SIZE):
            batch = rel_paths[i : i + RESUME_BATCH_SIZE]
            hashes, files_content = self._run_pipeline(rel_paths=batch)
            all_path_hashes.update(hashes)
            all_files_content.extend(files_content)
            self._state.save_progress(
                full_rel_paths=full_rel_paths,
                processed_count=i + len(batch),
            )

        return all_path_hashes, all_files_content

    def _update(
        self,
        paths_to_add: list[Path],
        file_hashes: dict[str, str],
    ) -> IndexResult:
        """Run pipeline over paths; update hashes and state."""
        rel_paths = [str(p.relative_to(self._repo_root)) for p in paths_to_add]
        self._state.start(
            branch=self._git.get_current_branch(),
            last_commit=self._git.get_head_commit(),
        )

        batch_hashes, files_content = self._run_batch_loop(
            rel_paths=rel_paths,
            full_rel_paths=rel_paths,
        )
        file_hashes.update(batch_hashes)
        self._state.file_hashes = file_hashes
        self._state.finish(
            last_commit=self._git.get_head_commit(),
            branch=self._git.get_current_branch(),
        )
        self._refresh_graph(changed_paths=rel_paths, files_content=files_content)
        return IndexResult(updated=len(batch_hashes))

    @timed("pipeline")
    def _run_pipeline(
        self,
        rel_paths: list[str],
    ) -> tuple[dict[str, str], list[tuple[str, str]]]:
        """Chunk, embed, store files; return (path_hashes, files_content)."""
        files_content: list[tuple[str, str]] = []

        with timed_phase("read"):
            for p in rel_paths:
                path = self._repo_root / p if not Path(p).is_absolute() else Path(p)
                if not path.is_file():
                    logger.warning("Skip (not a file): %s", p)
                    continue
                try:
                    content = read_from_path(path)
                    files_content.append((p, content))
                except Exception as e:
                    logger.warning("Skip (read failed) %s: %s", p, e)

        if not files_content:
            return {}, []

        path_hashes = {p: hash_content(content) for p, content in files_content}

        paths_to_replace = list({p for p, _ in files_content})
        self._store.delete_by_paths(paths_to_replace)

        with timed_phase("chunking"):
            chunks = []
            for p, content in files_content:
                chunks.extend(chunk_file(p, content))

        if not chunks:
            logger.info("Pipeline done: 0 chunks in %d files", len(files_content))
            return path_hashes, files_content

        texts = [format_chunk_for_embedding(c) for c in chunks]
        with timed_phase("embedding"):
            embeddings = self._embedder.embed(texts, task=EmbedTask.DOCUMENT)

        with timed_phase("storing"):
            self._store.insert_chunks(chunks, embeddings)

        logger.info(
            "Pipeline done: %d chunks in %d files", len(chunks), len(files_content)
        )
        return path_hashes, files_content

    def _refresh_graph(
        self,
        changed_paths: list[str] | None = None,
        files_content: list[tuple[str, str]] | None = None,
    ) -> None:
        """Rebuild and save code graph."""
        try:
            build_and_save_graph(
                self._repo_root,
                changed_paths=changed_paths,
                files_content=files_content,
            )
        except Exception as e:
            logger.warning("Graph refresh failed: %s", e)

    def maintain(self) -> dict[str, Any]:
        """Run store maintenance."""
        if not index_exists(self._index_dir):
            return {}
        return self._store.maintain()

    def index_exists(self) -> bool:
        """Return True if index exists."""
        return index_exists(self._index_dir)

    def _should_resume_full_build(self) -> bool:
        """Return True when meta indicates an interrupted full build to finish."""
        meta = self._state.current_state
        if meta is None or meta.state == MetaState.ERRORED:
            return False
        if not (meta.is_in_progress() or meta.is_incomplete()):
            return False
        run = meta.current_run
        if run.paths_to_process:
            return True
        return meta.is_in_progress()

    def ensure_index(self) -> IndexResult:
        """Build full index if missing; else incremental."""
        if not self.index_exists():
            return self.build_full()
        if self._should_resume_full_build():
            return self.build_full()
        return self.update_incremental()

    def error(self, exc: str) -> None:
        """Mark run as errored."""
        self._state.set_errored(exc=exc)
