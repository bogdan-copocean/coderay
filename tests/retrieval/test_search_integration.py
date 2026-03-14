"""Integration test: build index then search."""

import pytest

from coderay.pipeline.indexer import Indexer
from coderay.retrieval.search import Retrieval


class TestSearchIntegration:
    def test_build_and_search(self, fake_git_repo, mock_embedder, app_config):
        if fake_git_repo is None:
            pytest.skip("no git")
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()
        assert indexer.current_state is not None

    def test_retrieval_no_index(self, mock_embedder, app_config):
        r = Retrieval(embedder=mock_embedder)
        assert r.chunk_count() == 0
        assert r.list_chunks() == []
