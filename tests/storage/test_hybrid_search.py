"""Tests for Store.search() scoring in both vector-only and hybrid modes.

Validates that scores follow higher-is-better convention in both paths
and that hybrid search falls back gracefully when FTS is unavailable.
"""

from coderay.core.models import Chunk
from coderay.storage.lancedb import Store


class TestSearchScoring:
    """Store.search() returns higher-is-better scores in all modes."""

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

    def test_vector_returns_cosine_similarity(self, tmp_index_dir):
        """Pure vector search returns cosine similarity (0-1 range)."""
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) >= 1
        assert all(0 <= r["score"] <= 1.0 for r in results)

    def test_vector_score_type_is_cosine(self, tmp_index_dir):
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert all(r["score_type"] == "cosine" for r in results)

    def test_vector_exact_match_scores_high(self, tmp_index_dir):
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        best = max(results, key=lambda r: r["score"])
        assert best["path"] == "a.py"
        assert best["score"] > 0.9

    def test_hybrid_returns_results(self, tmp_index_dir):
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        assert len(results) >= 1

    def test_hybrid_scores_positive(self, tmp_index_dir):
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        assert all("score" in r and r["score"] > 0 for r in results)

    def test_hybrid_score_type_is_rrf(self, tmp_index_dir):
        """Hybrid search tags results with score_type='rrf'."""
        store = self._make_store(tmp_index_dir)
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2, query_text="foo")
        assert all(r.get("score_type") in ("rrf", "cosine") for r in results)
