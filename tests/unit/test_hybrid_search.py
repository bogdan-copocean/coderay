"""Tests for native hybrid search in the store.

LanceDB's native FTS + RRF hybrid is tested via integration tests.
This module validates the Store.search() API contract when hybrid
is requested but FTS index may not be available (graceful fallback).
"""

import pytest

from indexer.core.models import Chunk
from indexer.storage.lancedb import Store


class TestHybridSearchFallback:
    """When FTS index is not created, hybrid should fall back to vector-only."""

    def _make_store(self, tmp_index_dir) -> Store:
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="foo",
                language="python",
                content="def foo(): pass",
            ),
            Chunk(
                path="b.py",
                start_line=1,
                end_line=3,
                symbol="bar",
                language="python",
                content="def bar(): pass",
            ),
        ]
        embeddings = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
        store.insert_chunks(chunks, embeddings)
        return store

    def test_search_with_query_text(self, tmp_index_dir):
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        assert len(results) >= 1

    def test_search_without_query_text(self, tmp_index_dir):
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) >= 1

    def test_results_have_score(self, tmp_index_dir):
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        assert all("score" in r for r in results)
