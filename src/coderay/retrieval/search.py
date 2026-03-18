from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from coderay.core.config import Config, get_config
from coderay.core.timing import timed_phase
from coderay.embedding.base import Embedder, load_embedder_from_config
from coderay.graph.builder import load_graph
from coderay.retrieval.boosting import StructuralBooster
from coderay.state.machine import IndexMeta
from coderay.state.version import check_index_version
from coderay.storage.lancedb import Store, index_exists

logger = logging.getLogger(__name__)


def deduplicate_by_containment(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove results whose line range fully contains a more specific result.

    When a class and one of its methods both appear in the result set
    (same file, parent line range fully encloses child), the outer
    (less specific) result is dropped.  The inner result is kept because
    it is the more targeted match.

    Args:
        results: Ranked search results (highest score first).

    Returns:
        Filtered list with outer duplicates removed, order preserved.
    """
    if len(results) <= 1:
        return results

    # Index results by file for O(n*m) comparison within each file
    by_file: dict[str, list[int]] = {}
    for i, r in enumerate(results):
        by_file.setdefault(r.get("path", ""), []).append(i)

    drop: set[int] = set()
    for indices in by_file.values():
        if len(indices) < 2:
            continue
        for i in indices:
            if i in drop:
                continue
            ri = results[i]
            ri_start, ri_end = ri["start_line"], ri["end_line"]
            for j in indices:
                if j == i or j in drop:
                    continue
                rj = results[j]
                rj_start, rj_end = rj["start_line"], rj["end_line"]
                # ri fully contains rj → drop ri (the outer one)
                if ri_start <= rj_start and ri_end >= rj_end:
                    drop.add(i)
                    break

    return [r for i, r in enumerate(results) if i not in drop]


class Retrieval:
    """Query interface for the semantic index."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        """Initialize retrieval from the application config."""
        self._config = get_config()
        self.index_dir = Path(self._config.index.path)
        self._explicit_embedder = embedder
        self._lazy_embedder: Embedder | None = None
        self._dimensions = self._config.embedder.dimensions
        self._booster = StructuralBooster.from_config()
        self._store: Store | None = None
        check_index_version(self.index_dir)

    @property
    def _embedder(self) -> Embedder:
        if self._explicit_embedder is not None:
            return self._explicit_embedder
        if self._lazy_embedder is None:
            self._lazy_embedder = load_embedder_from_config()
        return self._lazy_embedder

    @property
    def config(self) -> Config:
        return self._config

    def _get_store(self) -> Store:
        if self._store is None:
            self._store = Store()
        return self._store

    def search(
        self,
        query: str,
        current_state: IndexMeta,
        *,
        top_k: int = 10,
        path_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search over the index."""
        if not index_exists(self.index_dir):
            logger.warning("No index at %s", self.index_dir)
            return []

        if current_state.is_incomplete() or current_state.is_in_progress():
            raise RuntimeError("Meta in progress; index might be stale")

        store = self._get_store()

        with timed_phase("embed"):
            query_vectors = self._embedder.embed([query])

        if not query_vectors:
            return []
        with timed_phase("vector_search"):
            results = store.search(
                query_embedding=query_vectors[0],
                top_k=top_k,
                path_prefix=path_prefix,
                query_text=query,
            )

        boosted = self._booster.boost(results)
        return deduplicate_by_containment(boosted)

    def load_graph(self) -> list[dict[str, Any]]:
        """Load graph edges from index_dir/graph.json. [] if missing."""
        graph = load_graph(self.index_dir)
        if graph is None:
            return []
        data = graph.to_dict()
        return data.get("edges", [])

    def chunk_count(self) -> int:
        """Total number of chunks in the index. Returns 0 if no index."""
        if not index_exists(self.index_dir):
            return 0
        return self._get_store().chunk_count()

    def list_chunks(
        self,
        *,
        limit: int = 500,
        path_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        """List indexed chunks (no vectors). For inspection/debugging."""
        if not index_exists(self.index_dir):
            return []
        return self._get_store().list_chunks(limit=limit, path_prefix=path_prefix)

    def chunks_by_path(self) -> dict[str, int]:
        """Return mapping of file path -> chunk count. Empty if no index."""
        if not index_exists(self.index_dir):
            return {}
        return self._get_store().chunks_by_path()
