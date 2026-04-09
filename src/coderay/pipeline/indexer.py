from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coderay.chunking.chunker import chunk_file
from coderay.core.config import ENV_REPO_ROOT, Config, get_config
from coderay.core.index_workspace import resolve_index_workspace
from coderay.core.timing import timed, timed_phase
from coderay.core.utils import (
    files_with_changed_content_keys,
    hash_content,
    read_from_path,
)
from coderay.embedding.base import Embedder, EmbedTask, load_embedder_from_config
from coderay.embedding.format import format_chunk_for_embedding
from coderay.graph.builder import build_and_save_graph
from coderay.state.machine import (
    CheckoutIndexState,
    IndexMeta,
    MetaState,
    StateMachine,
)
from coderay.state.version import check_index_version, write_index_version
from coderay.storage.lancedb import Store, index_exists
from coderay.vcs.git import WorkspaceGit

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
        self._workspace = resolve_index_workspace(self._repo_root, self._config)
        self._workspace_git = WorkspaceGit(self._workspace)
        self._state = StateMachine()
        self._embedder = embedder or load_embedder_from_config()
        self._store = Store()
        check_index_version(self._index_dir)

    def _checkout_states_from_git(self) -> tuple[CheckoutIndexState, ...]:
        """Build CheckoutIndexState rows from current git HEAD."""
        heads = self._workspace_git.head_commits()
        branches = self._workspace_git.current_branches()
        return tuple(
            CheckoutIndexState(
                alias=c.alias,
                commit=heads.get(c.alias) or "",
                branch=branches.get(c.alias) or "",
                is_primary=c.is_primary_checkout,
            )
            for c in self._workspace.roots
        )

    def _stored_commits_by_alias(self) -> dict[str, str | None]:
        """Return last indexed commit per checkout alias for incremental updates."""
        cur = self._state.current_state
        if not cur:
            return {}
        return {s.alias: (s.commit or None) for s in cur.sources}

    def _finish_heads(self) -> None:
        """Persist current HEAD commits and branches for all checkouts."""
        self._state.finish(sources=self._checkout_states_from_git())

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

    def _filter_excluded_keyed(
        self, keyed: list[tuple[str, Path]]
    ) -> list[tuple[str, Path]]:
        """Remove paths matching index.exclude_patterns (per-repo relative paths)."""
        by_alias = self._workspace.by_alias()
        out: list[tuple[str, Path]] = []
        for key, path in keyed:
            aid, _ = key.split("/", 1)
            checkout = by_alias[aid]
            rel = str(path.relative_to(checkout.repo_root))
            if not self._workspace.index_exclude.match_file(rel):
                out.append((key, path))
        return out

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
                self._finish_heads()
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

            discovered = self._workspace_git.discover_files()
            keyed = self._filter_excluded_keyed(discovered)
            if not keyed:
                logger.warning("No source files found for configured index roots")
                return IndexResult(cached=len(self._state.file_hashes))

            rel_paths = [k for k, _ in keyed]
            paths_to_process = rel_paths
            processed_count = 0
            self._state.start(sources=self._checkout_states_from_git())

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

        self._finish_heads()
        write_index_version(self._index_dir)
        self._refresh_graph(files_content=all_files_content)
        return IndexResult(updated=len(self._state.file_hashes))

    def update_incremental(self) -> IndexResult:
        """Incremental update: reconcile scope against config, then re-index."""

        self._state.set_incomplete()

        # Scope reconciliation: .coderay.toml is the source of truth.
        desired = self._workspace_git.discover_files()
        desired = self._filter_excluded_keyed(desired)
        desired_map = dict(desired)
        desired_keys = set(desired_map)

        file_hashes = self._state.file_hashes.copy()
        indexed_keys = set(file_hashes)

        stale_keys = indexed_keys - desired_keys
        new_in_scope = desired_keys - indexed_keys

        # Git-diff for content changes within existing scope.
        to_add, to_remove = self._workspace_git.get_files_to_index(
            self._stored_commits_by_alias()
        )
        to_add = self._filter_excluded_keyed(to_add)

        # Merge removes: git-diff removes + stale from scope change.
        all_removes = sorted(stale_keys | set(to_remove))
        if all_removes:
            self._store.delete_by_paths(all_removes)
        for k in all_removes:
            file_hashes.pop(k, None)
        self._state.file_hashes = file_hashes

        # Merge adds: git-diff adds + newly-in-scope files.
        to_add_map = dict(to_add)
        for k in new_in_scope:
            if k not in to_add_map:
                to_add_map[k] = desired_map[k]
        merged_adds = sorted(to_add_map.items())

        changed_files = files_with_changed_content_keys(merged_adds, file_hashes)

        if not changed_files and not all_removes:
            self._finish_heads()
            self._refresh_graph()
            logger.info("Nothing to update")
            return IndexResult(cached=len(self._state.file_hashes))

        if not changed_files:
            self._finish_heads()
            self._refresh_graph(removed_paths=all_removes)
            logger.info("Deindexed %d file(s)", len(all_removes))
            return IndexResult(
                removed=len(all_removes),
                cached=len(self._state.file_hashes),
            )

        result = self._update(
            paths_to_add=changed_files,
            file_hashes=file_hashes,
            removed_paths=all_removes if all_removes else None,
        )
        result.removed = len(all_removes)
        return result

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
        paths_to_add: list[tuple[str, Path]],
        file_hashes: dict[str, str],
        removed_paths: list[str] | None = None,
    ) -> IndexResult:
        """Run pipeline over paths; update hashes and state."""
        rel_paths = [k for k, _ in paths_to_add]
        self._state.start(sources=self._checkout_states_from_git())

        batch_hashes, files_content = self._run_batch_loop(
            rel_paths=rel_paths,
            full_rel_paths=rel_paths,
        )
        file_hashes.update(batch_hashes)
        self._state.file_hashes = file_hashes
        self._finish_heads()
        self._refresh_graph(
            changed_paths=rel_paths,
            removed_paths=removed_paths,
            files_content=files_content,
        )
        return IndexResult(updated=len(batch_hashes))

    @timed("pipeline")
    def _run_pipeline(
        self,
        rel_paths: list[str],
    ) -> tuple[dict[str, str], list[tuple[str, str]]]:
        """Chunk, embed, store files; return (path_hashes, files_content)."""
        files_content: list[tuple[str, str]] = []

        with timed_phase("pipeline", log=False) as tp_pipe:
            with timed_phase("read"):
                for p in rel_paths:
                    try:
                        path = self._workspace.resolve_logical(p)
                    except Exception:
                        logger.warning("Skip (bad logical path): %s", p)
                        continue
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
                logger.info(
                    "Pipeline done: 0 chunks in %d files (%.2fs)",
                    len(files_content),
                    tp_pipe.elapsed_so_far(),
                )
                return path_hashes, files_content

            texts = [format_chunk_for_embedding(c) for c in chunks]
            with timed_phase("embedding"):
                embeddings = self._embedder.embed(texts, task=EmbedTask.DOCUMENT)

            with timed_phase("storing"):
                self._store.insert_chunks(chunks, embeddings)

        logger.info(
            "Pipeline done: %d chunks in %d files (%.2fs)",
            len(chunks),
            len(files_content),
            tp_pipe.elapsed,
        )
        return path_hashes, files_content

    def _refresh_graph(
        self,
        changed_paths: list[str] | None = None,
        removed_paths: list[str] | None = None,
        files_content: list[tuple[str, str]] | None = None,
    ) -> None:
        """Rebuild and save code graph."""
        try:
            build_and_save_graph(
                self._workspace,
                changed_paths=changed_paths,
                removed_paths=removed_paths,
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
        return bool(meta.is_in_progress())

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
