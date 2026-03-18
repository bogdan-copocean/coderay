from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

from coderay.core.config import Config, get_config
from coderay.core.timing import timed_phase
from coderay.embedding.base import Embedder, load_embedder_from_config
from coderay.graph.builder import load_graph
from coderay.retrieval.boosting import StructuralBooster
from coderay.retrieval.models import SearchResult, is_test_path
from coderay.state.machine import IndexMeta
from coderay.state.version import check_index_version
from coderay.storage.lancedb import Store, index_exists

logger = logging.getLogger(__name__)

# Score-gap ratio: if a result's score drops below this fraction of
# the previous result's score, it and all subsequent results are
# flagged as low confidence.  Works for both RRF and vector scores
# because it measures *consecutive* relative drop, not an absolute
# distance from the top.
_SCORE_DROP_RATIO = 0.5


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
        include_tests: bool = True,
    ) -> list[SearchResult]:
        """Semantic search over the index.

        Args:
            query: Natural language search query.
            current_state: Current index metadata (must be complete).
            top_k: Maximum results to return from the vector store.
            path_prefix: Restrict results to paths under this directory.
            include_tests: When False, test files are excluded from results.

        Returns:
            Ranked list of SearchResult DTOs, deduplicated and annotated
            with a low_confidence flag where appropriate.
        """
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
            raw_results = store.search(
                query_embedding=query_vectors[0],
                top_k=top_k,
                path_prefix=path_prefix,
                query_text=query,
            )

        boosted = self._booster.boost(raw_results)
        results = [SearchResult.from_raw(r) for r in boosted]
        results = self._deduplicate_by_containment(results)

        if not include_tests:
            results = [r for r in results if not is_test_path(r.path)]

        results = self._mark_low_confidence(results)
        return results

    @staticmethod
    def _deduplicate_by_containment(
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Remove results whose line range fully contains a more specific result.

        When a class and one of its methods both appear in the result set
        (same file, parent line range fully encloses child), the outer
        (less specific) result is dropped because it is redundant.

        Args:
            results: Ranked results (highest score first).

        Returns:
            Filtered list with outer duplicates removed, order preserved.
        """
        if len(results) <= 1:
            return results

        # Group result indices by file so containment checks only
        # run within the same file.
        by_file: dict[str, list[int]] = {}
        for i, r in enumerate(results):
            by_file.setdefault(r.path, []).append(i)

        drop: set[int] = set()
        for indices in by_file.values():
            if len(indices) < 2:
                continue
            for i in indices:
                if i in drop:
                    continue
                for j in indices:
                    if j == i or j in drop:
                        continue
                    # If result[i] fully contains result[j], drop the
                    # outer (i) and keep the more specific inner (j).
                    if results[i].contains(results[j]):
                        drop.add(i)
                        break

        return [r for i, r in enumerate(results) if i not in drop]

    @staticmethod
    def _mark_low_confidence(
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Flag results after a significant score drop.

        Walks the ranked list and compares each result's score to its
        predecessor.  When the ratio drops below ``_SCORE_DROP_RATIO``
        (i.e. the score more than halves between consecutive results),
        that result and everything below it is flagged.

        This heuristic adapts to any score scale (RRF, cosine, hybrid)
        because it measures relative consecutive drops rather than an
        absolute distance from the top score.

        Args:
            results: Ranked results (highest score first).
        """
        if len(results) <= 1:
            return results

        cutoff_idx: int | None = None
        for i in range(1, len(results)):
            prev_score = results[i - 1].score
            if prev_score <= 0:
                continue
            if results[i].score / prev_score < _SCORE_DROP_RATIO:
                cutoff_idx = i
                break

        if cutoff_idx is None:
            return results

        return [
            replace(r, low_confidence=True) if i >= cutoff_idx else r
            for i, r in enumerate(results)
        ]

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
