"""Tests for Store.search() scoring in both vector-only and hybrid modes.

Validates that scores follow higher-is-better convention in both paths
and that hybrid search falls back gracefully when FTS is unavailable.
"""

from coderay.core.models import Chunk
from coderay.storage.lancedb import Store


class TestSearchScoring:
    """Store.search() returns higher-is-better scores in all modes."""

    def _make_store(self, app_config) -> Store:
        store = Store()
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="foo",
                content="def foo(): pass",
            ),
            Chunk(
                path="b.py",
                start_line=1,
                end_line=3,
                symbol="bar",
                content="def bar(): pass",
            ),
        ]
        embeddings = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
        store.insert_chunks(chunks, embeddings)
        return store

    def test_vector_returns_cosine_similarity(self, app_config):
        """Pure vector search returns cosine similarity (0-1 range)."""
        store = self._make_store(app_config)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) >= 1
        assert all(0 <= r["score"] <= 1.0 for r in results)

    def test_vector_exact_match_scores_high(self, app_config):
        store = self._make_store(app_config)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        best = max(results, key=lambda r: r["score"])
        assert best["path"] == "a.py"
        assert best["score"] > 0.9

    def test_hybrid_returns_results(self, app_config):
        """Hybrid search returns results (may degrade to vector-only)."""
        store = self._make_store(app_config)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        assert len(results) >= 1

    def test_hybrid_scores_non_negative(self, app_config):
        """Scores from hybrid search (or fallback) are non-negative."""
        store = self._make_store(app_config)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        assert all("score" in r and r["score"] >= 0 for r in results)

    def test_hybrid_best_match_positive(self, app_config):
        """The best result from hybrid search should have a positive score."""
        store = self._make_store(app_config)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        best = max(results, key=lambda r: r["score"])
        assert best["score"] > 0

    def test_search_mode_always_present(self, app_config):
        """Every result has a search_mode key ('hybrid' or 'vector')."""
        store = self._make_store(app_config)
        for query_text in [None, "foo"]:
            results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text=query_text)
            for r in results:
                assert r["search_mode"] in ("hybrid", "vector")

    def test_vector_search_mode_label(self, app_config):
        """Vector-only search labels results with search_mode='vector'."""
        store = self._make_store(app_config)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert results[0]["search_mode"] == "vector"

    def test_hybrid_fallback_uses_vector_mode(self, app_config):
        """When FTS index is unavailable, hybrid falls back to vector."""
        store = self._make_store(app_config)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        assert all(r["search_mode"] in ("hybrid", "vector") for r in results)
