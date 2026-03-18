from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from coderay.core.config import Config, get_config
from coderay.core.errors import IndexStaleError
from coderay.core.timing import timed_phase
from coderay.embedding.base import Embedder, EmbedTask, load_embedder_from_config
from coderay.retrieval.boosting import StructuralBooster
from coderay.retrieval.models import Relevance, SearchResult, is_test_path
from coderay.state.machine import IndexMeta
from coderay.state.version import check_index_version
from coderay.storage.lancedb import Store, index_exists

logger = logging.getLogger(__name__)

# If a result's score drops below this fraction of the previous
# result's score, it marks a relevance tier boundary.
_SCORE_DROP_RATIO = 0.5


class Retrieval:
    """Orchestrate semantic search: embed, query, boost, deduplicate, rank."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        """Initialize; load embedder from config if None."""
        self._config = get_config()
        self.index_dir = Path(self._config.index.path)
        self._explicit_embedder = embedder
        self._lazy_embedder: Embedder | None = None
        self._dimensions = self._config.embedder.dimensions
        self._booster = StructuralBooster.from_config()
        self._store: Store | None = None
        self._version_checked = False

    @property
    def _embedder(self) -> Embedder:
        """Return embedder (lazy load)."""
        if self._explicit_embedder is not None:
            return self._explicit_embedder
        if self._lazy_embedder is None:
            self._lazy_embedder = load_embedder_from_config()
        return self._lazy_embedder

    @property
    def config(self) -> Config:
        """Return config."""
        return self._config

    def _get_store(self) -> Store:
        """Return store (lazy create)."""
        if self._store is None:
            self._store = Store()
        return self._store

    def _ensure_version_checked(self) -> None:
        """Run version check once on first search."""
        if not self._version_checked:
            check_index_version(self.index_dir)
            self._version_checked = True

    def search(
        self,
        query: str,
        current_state: IndexMeta,
        *,
        top_k: int = 10,
        path_prefix: str | None = None,
        include_tests: bool = True,
    ) -> list[SearchResult]:
        """Search index; return ranked, deduplicated results."""
        if not index_exists(self.index_dir):
            logger.warning("No index at %s", self.index_dir)
            return []

        if current_state.is_incomplete() or current_state.is_in_progress():
            raise IndexStaleError(
                "Index metadata indicates an in-progress or incomplete build. "
                "Wait for the build to finish or re-run 'coderay build'."
            )

        self._ensure_version_checked()
        store = self._get_store()

        with timed_phase("embed"):
            query_vectors = self._embedder.embed([query], task=EmbedTask.QUERY)

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

        results = self._assign_relevance(results)
        return results

    @staticmethod
    def _deduplicate_by_containment(
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Drop results whose range encloses a more specific hit."""
        if len(results) <= 1:
            return results

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
                    if results[i].contains(results[j]):
                        drop.add(i)
                        break

        return [r for i, r in enumerate(results) if i not in drop]

    @staticmethod
    def _assign_relevance(
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Assign relevance tiers from score drops."""
        if len(results) <= 1:
            return results

        boundaries: list[int] = []
        for i in range(1, len(results)):
            prev_score = results[i - 1].score
            if prev_score <= 0:
                continue
            if results[i].score / prev_score < _SCORE_DROP_RATIO:
                boundaries.append(i)
                if len(boundaries) == 2:
                    break

        if not boundaries:
            return results

        tiers: list[Relevance] = ["high"] * len(results)
        for i in range(boundaries[0], len(results)):
            tiers[i] = "medium"
        if len(boundaries) > 1:
            for i in range(boundaries[1], len(results)):
                tiers[i] = "low"

        return [
            replace(r, relevance=tier) for r, tier in zip(results, tiers, strict=True)
        ]
