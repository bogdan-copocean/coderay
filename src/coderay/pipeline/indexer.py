from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coderay.chunking.chunker import chunk_file
from coderay.core.config import Config, get_config
from coderay.core.timing import timed, timed_phase
from coderay.core.utils import files_with_changed_content, hash_content, read_from_path
from coderay.embedding.base import Embedder, EmbedTask, load_embedder_from_config
from coderay.graph.builder import build_and_save_graph
from coderay.state.machine import IndexMeta, StateMachine
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
        self._repo_root = Path(repo_root)
        self._config = get_config()
        self._index_dir = Path(self._config.index.path)
        self._git = Git(self._repo_root)
        self._state = StateMachine()
        self._embedder = embedder or load_embedder_from_config()
        self._store = Store()
        check_index_version(self._index_dir)

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
                self._state.finish(
                    last_commit=self._git.get_head_commit(),
                    branch=self._git.get_current_branch(),
                )
                write_index_version(self._index_dir)
                self._refresh_graph()
                return IndexResult(cached=len(self._state.file_hashes))
            paths_to_process = paths_remaining
            rel_paths = saved_paths
        else:
            self._state.set_incomplete()
            self._store.clear()

            py_files = self._git.discover_files()
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

        texts = [c.content for c in chunks]
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

    def update_paths(
        self,
        changed: list[str],
        removed: list[str] | None = None,
    ) -> IndexResult:
        """Update index for explicit paths (used by watcher)."""
        self._state.set_incomplete()
        file_hashes = self._state.file_hashes.copy()

        removed = removed or []
        if removed:
            self._store.delete_by_paths(removed)
            for p in removed:
                file_hashes.pop(p, None)
            self._state.file_hashes = file_hashes

        if not changed:
            self._state.finish(
                last_commit=self._git.get_head_commit(),
                branch=self._git.get_current_branch(),
            )
            if removed:
                self._refresh_graph()
            return IndexResult(removed=len(removed))

        paths_to_add = [self._repo_root / p for p in changed]
        existing = files_with_changed_content(
            repo=self._repo_root, paths=paths_to_add, file_hashes=file_hashes
        )

        if not existing and not removed:
            self._state.finish(
                last_commit=self._git.get_head_commit(),
                branch=self._git.get_current_branch(),
            )
            return IndexResult(cached=len(file_hashes))

        if existing:
            result = self._update(
                paths_to_add=existing,
                file_hashes=file_hashes,
            )
            result.removed = len(removed)
            return result

        self._state.finish(
            last_commit=self._git.get_head_commit(),
            branch=self._git.get_current_branch(),
        )
        self._refresh_graph()
        return IndexResult(removed=len(removed))

    def maintain(self) -> dict[str, Any]:
        """Run store maintenance."""
        if not index_exists(self._index_dir):
            return {}
        return self._store.maintain()

    def index_exists(self) -> bool:
        """Return True if index exists."""
        return index_exists(self._index_dir)

    def ensure_index(self) -> IndexResult:
        """Build full index if missing; else incremental."""
        if not self.index_exists():
            return self.build_full()
        return self.update_incremental()

    def error(self, exc: str) -> None:
        """Mark run as errored."""
        self._state.set_errored(exc=exc)
