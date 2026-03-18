"""Integration test: build index then search."""

import pytest

from coderay.pipeline.indexer import Indexer
from coderay.storage.lancedb import Store


class TestSearchIntegration:
    def test_build_and_search(self, fake_git_repo, mock_embedder, app_config):
        if fake_git_repo is None:
            pytest.skip("no git")
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()
        assert indexer.current_state is not None

    def test_no_index_store_empty(self, mock_embedder, app_config):
        """Store returns 0 chunks when no index exists."""
        store = Store()
        assert store.chunk_count() == 0
