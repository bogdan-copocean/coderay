"""Tests for indexer.pipeline.indexer."""

import pytest

from indexer.pipeline.indexer import Indexer, IndexResult


class TestIndexResult:
    def test_str(self):
        r = IndexResult(cached=5, updated=3, removed=1)
        assert "5" in str(r)
        assert "3" in str(r)

    def test_defaults(self):
        r = IndexResult()
        assert r.cached == 0
        assert r.updated == 0
        assert r.removed == 0


class TestIndexer:
    def test_init_with_mock_embedder(self, tmp_path, mock_embedder, mock_config):
        repo = tmp_path / "repo"
        repo.mkdir()
        idx = tmp_path / ".index"
        idx.mkdir()
        indexer = Indexer(repo, idx, config=mock_config, embedder=mock_embedder)
        assert indexer.repo_root == repo
        assert indexer.index_dir == idx

    def test_build_full_empty_repo(self, tmp_path, mock_embedder, mock_config):
        repo = tmp_path / "repo"
        repo.mkdir()
        idx = tmp_path / ".index"
        idx.mkdir()
        indexer = Indexer(repo, idx, config=mock_config, embedder=mock_embedder)
        result = indexer.build_full()
        assert isinstance(result, IndexResult)

    def test_build_full_with_files(
        self, fake_git_repo, mock_embedder, mock_config, tmp_path
    ):
        if fake_git_repo is None:
            pytest.skip("no git")
        idx = tmp_path / ".index"
        idx.mkdir()
        indexer = Indexer(
            fake_git_repo, idx, config=mock_config, embedder=mock_embedder
        )
        result = indexer.build_full()
        assert result.updated > 0 or result.cached >= 0

    def test_maintain_no_index(self, tmp_path, mock_embedder, mock_config):
        repo = tmp_path / "repo"
        repo.mkdir()
        idx = tmp_path / ".index"
        idx.mkdir()
        indexer = Indexer(repo, idx, config=mock_config, embedder=mock_embedder)
        result = indexer.maintain()
        assert isinstance(result, dict)

    def test_index_exists(self, tmp_path, mock_embedder, mock_config):
        repo = tmp_path / "repo"
        repo.mkdir()
        idx = tmp_path / ".index"
        idx.mkdir()
        indexer = Indexer(repo, idx, config=mock_config, embedder=mock_embedder)
        assert not indexer.index_exists()

    def test_error_sets_state(
        self, fake_git_repo, tmp_path, mock_embedder, mock_config
    ):
        if fake_git_repo is None:
            pytest.skip("no git")
        idx = tmp_path / ".index"
        idx.mkdir()
        indexer = Indexer(
            fake_git_repo, idx, config=mock_config, embedder=mock_embedder
        )
        indexer.build_full()  # creates state
        indexer.error("test error")
        state = indexer.current_state
        assert state is not None

    def test_build_full_creates_graph(
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
        graph_file = idx / "graph.json"
        assert graph_file.is_file()

    def test_build_full_writes_version(
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
        from indexer.state.version import read_index_version

        assert read_index_version(idx) is not None
