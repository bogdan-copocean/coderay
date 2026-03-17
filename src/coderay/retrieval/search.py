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
