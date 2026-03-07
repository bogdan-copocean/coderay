from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from coderay.core.config import get_embedding_dimensions, load_config
from coderay.embedding.base import Embedder, load_embedder_from_config
from coderay.graph.builder import load_graph
from coderay.retrieval.boosting import StructuralBooster
from coderay.state.machine import IndexMeta
from coderay.state.version import check_index_version
from coderay.storage.lancedb import Store, index_exists

logger = logging.getLogger(__name__)


class Retrieval:
    """Query interface for the semantic index."""

    def __init__(
        self,
        index_dir: str | Path,
        config: dict[str, Any] | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        """Initialize retrieval for the given index."""
        self.index_dir = Path(index_dir)
        self._config = config or load_config(self.index_dir)
        self._explicit_embedder = embedder
        self._lazy_embedder: Embedder | None = None
        self._dimensions = get_embedding_dimensions(self._config)
        self._booster = StructuralBooster.from_config(self._config)
        self._store: Store | None = None
        check_index_version(self.index_dir)

    @property
    def _embedder(self) -> Embedder:
        if self._explicit_embedder is not None:
            return self._explicit_embedder
        if self._lazy_embedder is None:
            self._lazy_embedder = load_embedder_from_config(self._config)
        return self._lazy_embedder

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def _get_store(self) -> Store:
        if self._store is None:
            self._store = Store(self.index_dir, dimensions=self._dimensions)
        return self._store

    def search(
        self,
        query: str,
        current_state: IndexMeta,
        *,
        top_k: int = 10,
        path_prefix: str | None = None,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search over the index."""
        if not index_exists(self.index_dir):
            logger.warning("No index at %s", self.index_dir)
            return []

        if current_state.is_incomplete() or current_state.is_in_progress():
            raise RuntimeError("Meta in progress; index might be stale")

        store = self._get_store()

        t0 = time.perf_counter()
        query_vectors = self._embedder.embed([query])
        logger.info("Query embed took %.3fs", time.perf_counter() - t0)

        if not query_vectors:
            return []
        t1 = time.perf_counter()
        results = store.search(
            query_embedding=query_vectors[0],
            top_k=top_k,
            path_prefix=path_prefix,
            language=language,
            query_text=query,
        )
        logger.info("Vector search took %.3fs", time.perf_counter() - t1)

        return self._booster.boost(results)

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
