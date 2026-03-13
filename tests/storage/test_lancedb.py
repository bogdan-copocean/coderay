"""Tests for indexer.storage.lancedb."""

import pytest

from coderay.core.models import Chunk
from coderay.storage.lancedb import Store, index_exists


class TestStore:
    def test_insert_and_count(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="foo",
                content="def foo(): pass",
            )
        ]
        embeddings = [[1.0, 2.0, 3.0, 4.0]]
        store.insert_chunks(chunks, embeddings)
        assert store.chunk_count() == 1

    def test_search(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="foo",
                content="def foo(): pass",
            )
        ]
        embeddings = [[1.0, 2.0, 3.0, 4.0]]
        store.insert_chunks(chunks, embeddings)
        results = store.search([1.0, 2.0, 3.0, 4.0], top_k=5)
        assert len(results) >= 1
        assert results[0]["symbol"] == "foo"
        assert "vector" not in results[0]

    def test_delete_by_paths(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="foo",
                content="x",
            ),
            Chunk(
                path="b.py",
                start_line=1,
                end_line=3,
                symbol="bar",
                content="y",
            ),
        ]
        embeddings = [[1.0] * 4, [2.0] * 4]
        store.insert_chunks(chunks, embeddings)
        store.delete_by_paths(["a.py"])
        assert store.chunk_count() == 1

    def test_list_chunks(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="foo",
                content="x",
            )
        ]
        store.insert_chunks(chunks, [[1.0] * 4])
        listed = store.list_chunks()
        assert len(listed) == 1
        assert "vector" not in listed[0]

    def test_chunks_by_path(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="f",
                content="x",
            ),
            Chunk(
                path="a.py",
                start_line=4,
                end_line=6,
                symbol="g",
                content="y",
            ),
            Chunk(
                path="b.py",
                start_line=1,
                end_line=3,
                symbol="h",
                content="z",
            ),
        ]
        embeddings = [[1.0] * 4, [2.0] * 4, [3.0] * 4]
        store.insert_chunks(chunks, embeddings)
        by_path = store.chunks_by_path()
        assert by_path["a.py"] == 2
        assert by_path["b.py"] == 1

    def test_clear(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="f",
                content="x",
            )
        ]
        store.insert_chunks(chunks, [[1.0] * 4])
        store.clear()
        assert store.chunk_count() == 0

    def test_dimension_mismatch_raises(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="f",
                content="x",
            )
        ]
        with pytest.raises(ValueError, match="dimension"):
            store.insert_chunks(chunks, [[1.0, 2.0]])

    def test_empty_insert_noop(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        store.insert_chunks([], [])
        assert store.chunk_count() == 0

    def test_length_mismatch_raises(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="f",
                content="x",
            )
        ]
        with pytest.raises(ValueError, match="mismatch"):
            store.insert_chunks(chunks, [])


class TestIndexExists:
    def test_no_index(self, tmp_path):
        assert not index_exists(tmp_path)

    def test_with_index(self, tmp_index_dir):
        store = Store(tmp_index_dir, dimensions=4)
        chunks = [
            Chunk(
                path="a.py",
                start_line=1,
                end_line=3,
                symbol="f",
                content="x",
            )
        ]
        store.insert_chunks(chunks, [[1.0] * 4])
        assert index_exists(tmp_index_dir)
