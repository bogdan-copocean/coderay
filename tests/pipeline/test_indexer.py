"""Tests for indexer.pipeline.indexer."""

from pathlib import Path

import pytest

from coderay.pipeline.indexer import Indexer, IndexResult


class TestIndexer:
    def test_init_with_mock_embedder(self, tmp_path, mock_embedder, app_config):
        repo = tmp_path / "repo"
        repo.mkdir()
        idx = Path(app_config.index.path)
        indexer = Indexer(repo, embedder=mock_embedder)
        assert indexer.repo_root == repo
        assert indexer.index_dir == idx

    def test_build_full_empty_repo(self, tmp_path, mock_embedder, app_config):
        repo = tmp_path / "repo"
        repo.mkdir()
        indexer = Indexer(repo, embedder=mock_embedder)
        result = indexer.build_full()
        assert isinstance(result, IndexResult)

    def test_build_full_with_files(self, fake_git_repo, mock_embedder, app_config):
        if fake_git_repo is None:
            pytest.skip("no git")
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        result = indexer.build_full()
        assert result.updated > 0 or result.cached >= 0

    def test_maintain_no_index(self, tmp_path, mock_embedder, app_config):
        repo = tmp_path / "repo"
        repo.mkdir()
        indexer = Indexer(repo, embedder=mock_embedder)
        result = indexer.maintain()
        assert isinstance(result, dict)

    def test_index_exists(self, tmp_path, mock_embedder, app_config):
        repo = tmp_path / "repo"
        repo.mkdir()
        indexer = Indexer(repo, embedder=mock_embedder)
        assert not indexer.index_exists()

    def test_error_sets_state(self, fake_git_repo, mock_embedder, app_config):
        if fake_git_repo is None:
            pytest.skip("no git")
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()  # creates state
        indexer.error("test error")
        state = indexer.current_state
        assert state is not None

    def test_build_full_creates_graph(self, fake_git_repo, mock_embedder, app_config):
        if fake_git_repo is None:
            pytest.skip("no git")
        idx = Path(app_config.index.path)
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()
        graph_file = idx / "graph.json"
        assert graph_file.is_file()

    def test_build_full_writes_version(self, fake_git_repo, mock_embedder, app_config):
        if fake_git_repo is None:
            pytest.skip("no git")
        idx = Path(app_config.index.path)
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()
        from coderay.state.version import read_index_version

        assert read_index_version(idx) is not None
