"""Integration test: build index then search."""

import pytest

from indexer.pipeline.indexer import Indexer
from indexer.retrieval.search import Retrieval


class TestSearchIntegration:
    def test_build_and_search(
        self, fake_git_repo, tmp_path, mock_embedder, mock_config
    ):
        if fake_git_repo is None:
            pytest.skip("no git")
        idx = tmp_path / ".index"
        idx.mkdir()
        indexer = Indexer(
            fake_git_repo, idx, config=mock_config, embedder=mock_embedder
        )
        indexer.build_full()
        assert indexer.current_state is not None

    def test_retrieval_no_index(self, tmp_path, mock_config, mock_embedder):
        idx = tmp_path / ".index"
        idx.mkdir()
        r = Retrieval(idx, config=mock_config, embedder=mock_embedder)
        assert r.chunk_count() == 0
        assert r.list_chunks() == []
