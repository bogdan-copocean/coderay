"""
Indexer: single entry point for building, updating, and maintaining the index.

Handles indexing (chunk, embed, store), metadata, call/import graph,
and store maintenance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from indexer.chunking.chunker import chunk_file
from indexer.core.config import get_embedding_dimensions, load_config
from indexer.core.timing import timed, timed_phase
from indexer.core.utils import files_with_changed_content, hash_content, read_from_path
from indexer.embedding.base import Embedder, load_embedder_from_config
from indexer.graph.builder import build_and_save_graph
from indexer.state.machine import IndexMeta, StateMachine
from indexer.state.version import check_index_version, write_index_version
from indexer.storage.lancedb import Store, index_exists
from indexer.vcs.git import Git

logger = logging.getLogger(__name__)

RESUME_BATCH_SIZE = 200
DEFAULT_REPO_ROOT = "."
DEFAULT_INDEX_DIR = ".index"


@dataclass
class IndexResult:
    cached: int = 0
    updated: int = 0
    removed: int = 0

    def __str__(self) -> str:
        return (
            f"Cached: {self.cached}, Updated: {self.updated},"
            f" Removed: {self.removed} chunks"
        )


class Indexer:
    """
    Builds and maintains the semantic index for a repository.

    Discovers Python files, chunks and embeds them, stores in the vector DB,
    and keeps meta and call/import graph up to date. Use build_full() or
    update_incremental(), then maintain() to reclaim space.
    """

    def __init__(
        self,
        repo_root: str | Path = DEFAULT_REPO_ROOT,
        index_dir: str | Path = DEFAULT_INDEX_DIR,
        config: dict[str, Any] | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        """
        Initialize the indexer.

        Args:
            repo_root: Path to the repository root. Defaults to current directory.
            index_dir: Path to the index directory (contains LanceDB, meta.json).
                Defaults to ".index".
            config: Optional config dict; if None, loaded from index_dir.
            embedder: Optional embedder instance (for testing).
                If None, built from config.
        """
        self._repo_root = Path(repo_root)
        self._index_dir = Path(index_dir)
        self._config = config or load_config(self._index_dir)
        self._git = Git(self._repo_root)
        self._state = StateMachine(self._index_dir)
        self._embedder = embedder or load_embedder_from_config(self._config)
        self._store = Store(
            self._index_dir, dimensions=get_embedding_dimensions(self._config)
        )
        check_index_version(self._index_dir)

    @property
    def config(self) -> dict[str, Any]:
        """Current config (embedder, index settings)."""
        return self._config

    @property
    def repo_root(self) -> Path:
        """Repository root path."""
        return self._repo_root

    @property
    def index_dir(self) -> Path:
        """Index directory path."""
        return self._index_dir

    @property
    def current_state(self) -> IndexMeta | None:
        return self._state.current_state

    @timed("full_build")
    def build_full(self) -> IndexResult:
        """
        Run a full rebuild: discover Python files, chunk, embed, and store.

        Supports resume from in_progress/incomplete: continues from
        processed_count without clearing the store. On branch switch,
        delegates to update_incremental().

        Returns:
            Tuple of (chunks indexed, elapsed seconds).
        """

        current = self._state.current_state
        last_branch = current.branch if current is not None else None
        branch_switched = self._git.is_branch_switched(last_branch=last_branch)
        if branch_switched:
            return self.update_incremental()

        current_run = current.current_run if current else None
        saved_paths = current_run.paths_to_process if current_run else []
        processed_count = current_run.processed_count if current_run else 0

        can_resume = (
            not branch_switched
            and self._state.is_in_progress
            and self._state.has_partial_progress
        )

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

        all_path_hashes = self._run_batch_loop(
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
        self._refresh_graph()
        return IndexResult(updated=len(self._state.file_hashes))

    def update_incremental(self) -> IndexResult:
        """
        Run an incremental update: only changed, added, or deleted files.

        Re-indexes changed files (idempotent), removes deleted paths, and
        refreshes meta and graph. On branch switch, syncs to the current branch.

        Returns:
            Tuple of (chunks indexed, elapsed seconds).
        """

        self._state.set_incomplete()

        current = self._state.current_state
        state_branch = current.branch if current else None
        active_branch = self._git.get_current_branch()

        if self._git.is_branch_switched(last_branch=state_branch):
            logger.info(
                "Branch switched %s -> %s; syncing index",
                state_branch,
                active_branch,
            )
            return self._sync_after_branch_switch()

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

    def _sync_after_branch_switch(self) -> IndexResult:
        """Sync index to current branch after switch. Returns (chunks, elapsed)."""
        file_hashes = self._state.file_hashes.copy()
        py_files = self._git.discover_files()

        # All .py files were deleted from git
        to_remove: list[str] = []
        if not py_files:
            to_remove = list(file_hashes)

        if to_remove:
            self._store.delete_by_paths(to_remove)
            index_result = IndexResult(removed=len(file_hashes))
            file_hashes.clear()

            self._state.file_hashes = file_hashes
            self._state.finish(
                last_commit=self._git.get_head_commit(),
                branch=self._git.get_current_branch(),
            )
            self._refresh_graph()
            return index_result

        rel_paths_current = {str(p.relative_to(self._repo_root)) for p in py_files}
        # Deleted files on current branch
        to_remove = [p for p in file_hashes if p not in rel_paths_current]
        if to_remove:
            self._store.delete_by_paths(to_remove)
            for p in to_remove:
                file_hashes.pop(p, None)

        changed_files = files_with_changed_content(
            repo=self._repo_root, paths=py_files, file_hashes=file_hashes
        )

        if not changed_files and not to_remove:
            self._state.finish(
                last_commit=self._git.get_head_commit(),
                branch=self._git.get_current_branch(),
            )
            self._refresh_graph()
            logger.info("Branch switch: index already in sync (no changes)")
            return IndexResult(cached=len(self._state.file_hashes))

        return self._update(
            paths_to_add=changed_files,
            file_hashes=file_hashes,
        )

    def _run_batch_loop(
        self,
        rel_paths: list[str],
        full_rel_paths: list[str],
    ) -> dict[str, str]:
        """
        Run the pipeline in batches over rel_paths and save progress.

        Args:
            rel_paths: Paths to process in this run (may be a subset for resume).
            full_rel_paths: Full list of paths (for save_progress resume info).

        Returns:
            Tuple of (total chunks indexed, path -> content_hash for processed paths).
        """
        all_path_hashes: dict[str, str] = {}

        for i in range(0, len(rel_paths), RESUME_BATCH_SIZE):
            batch = rel_paths[i : i + RESUME_BATCH_SIZE]
            all_path_hashes.update(self._run_pipeline(rel_paths=batch))
            self._state.save_progress(
                full_rel_paths=full_rel_paths,
                processed_count=i + len(batch),
            )

        return all_path_hashes

    def _update(
        self,
        paths_to_add: list[Path],
        file_hashes: dict[str, str],
    ) -> IndexResult:
        """
        Run the pipeline over paths_to_add, update file_hashes and state, then finish.

        Args:
            paths_to_add: Paths (absolute) to re-index.
            file_hashes: Dict to update with new hashes (updated in place and saved).

        Returns:
            Total chunks indexed.
        """
        rel_paths = [str(p.relative_to(self._repo_root)) for p in paths_to_add]
        self._state.start(
            branch=self._git.get_current_branch(),
            last_commit=self._git.get_head_commit(),
        )

        batch_hashes = self._run_batch_loop(
            rel_paths=rel_paths,
            full_rel_paths=rel_paths,
        )
        file_hashes.update(batch_hashes)
        self._state.file_hashes = file_hashes
        self._state.finish(
            last_commit=self._git.get_head_commit(),
            branch=self._git.get_current_branch(),
        )
        self._refresh_graph(changed_paths=rel_paths)
        return IndexResult(updated=len(batch_hashes))

    @timed("pipeline")
    def _run_pipeline(
        self,
        rel_paths: list[str],
    ) -> dict[str, str]:
        """
        Chunk, embed, and store the given files. Idempotent per path.

        Removes existing chunks for these paths before insert.
        Language is auto-detected from file extension.

        Args:
            rel_paths: Relative paths (strings) under repo_root.

        Returns:
            Dict mapping relative path -> content hash for processed files.
        """
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
            return {}

        path_hashes = {p: hash_content(content) for p, content in files_content}

        paths_to_replace = list({p for p, _ in files_content})
        self._store.delete_by_paths(paths_to_replace)

        with timed_phase("chunking"):
            chunks = []
            for p, content in files_content:
                chunks.extend(chunk_file(p, content))

        if not chunks:
            logger.info("Pipeline done: 0 chunks in %d files", len(files_content))
            return path_hashes

        texts = [c.content for c in chunks]
        with timed_phase("embedding"):
            embeddings = self._embedder.embed(texts)

        with timed_phase("storing"):
            self._store.insert_chunks(chunks, embeddings)

        logger.info(
            "Pipeline done: %d chunks in %d files", len(chunks), len(files_content)
        )
        return path_hashes

    def _refresh_graph(self, changed_paths: list[str] | None = None) -> None:
        try:
            build_and_save_graph(
                self._repo_root,
                self._index_dir,
                changed_paths=changed_paths,
            )
        except Exception as e:
            logger.warning("Graph refresh failed: %s", e)

    def maintain(self) -> dict[str, Any]:
        """
        Run store maintenance (cleanup old versions, compact).

        Returns:
            Dict with keys e.g. cleanup_done, compact_done, error_cleanup,
            error_compact.
        """
        if not index_exists(self._index_dir):
            return {}
        return self._store.maintain()

    def index_exists(self) -> bool:
        """
        Return True if the index (LanceDB table) exists at index_dir.

        Returns:
            True if the chunks table exists.
        """
        return index_exists(self._index_dir)

    def error(self, exc: str) -> None:
        self._state.set_errored(exc=exc)
