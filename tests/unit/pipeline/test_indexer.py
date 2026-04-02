"""Tests for indexer.pipeline.indexer."""

import json
import subprocess
from pathlib import Path

import pytest

from coderay.core.config import render_default_toml
from coderay.pipeline.indexer import Indexer, IndexResult


def _write_coderay_toml(repo: Path) -> None:
    """Match MockEmbedder dimensions to Store expectations."""
    text = render_default_toml(repo).replace("dimensions = 384", "dimensions = 4")
    (repo / ".coderay.toml").write_text(text, encoding="utf-8")


class TestIndexer:
    def test_init_with_mock_embedder(self, tmp_path, mock_embedder):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".coderay.toml").write_text(render_default_toml(repo))
        indexer = Indexer(repo, embedder=mock_embedder)
        assert indexer.repo_root == repo
        assert indexer.index_dir == (repo / ".coderay").resolve()

    def test_build_full_empty_repo(self, tmp_path, mock_embedder):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".coderay.toml").write_text(render_default_toml(repo))
        indexer = Indexer(repo, embedder=mock_embedder)
        result = indexer.build_full()
        assert isinstance(result, IndexResult)

    def test_build_full_with_files(self, fake_git_repo, mock_embedder):
        if fake_git_repo is None:
            pytest.skip("no git")
        _write_coderay_toml(fake_git_repo)
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        result = indexer.build_full()
        assert result.updated > 0 or result.cached >= 0

    def test_maintain_no_index(self, tmp_path, mock_embedder):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".coderay.toml").write_text(render_default_toml(repo))
        indexer = Indexer(repo, embedder=mock_embedder)
        result = indexer.maintain()
        assert isinstance(result, dict)

    def test_index_exists(self, tmp_path, mock_embedder):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".coderay.toml").write_text(render_default_toml(repo))
        indexer = Indexer(repo, embedder=mock_embedder)
        assert not indexer.index_exists()

    def test_error_sets_state(self, fake_git_repo, mock_embedder):
        if fake_git_repo is None:
            pytest.skip("no git")
        _write_coderay_toml(fake_git_repo)
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()  # creates state
        indexer.error("test error")
        state = indexer.current_state
        assert state is not None

    def test_build_full_creates_graph(self, fake_git_repo, mock_embedder):
        if fake_git_repo is None:
            pytest.skip("no git")
        _write_coderay_toml(fake_git_repo)
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()
        graph_file = (fake_git_repo / ".coderay" / "graph.json").resolve()
        assert graph_file.is_file()

    def test_build_full_writes_version(self, fake_git_repo, mock_embedder):
        if fake_git_repo is None:
            pytest.skip("no git")
        _write_coderay_toml(fake_git_repo)
        idx = (fake_git_repo / ".coderay").resolve()
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()
        from coderay.state.version import read_index_version

        assert read_index_version(idx) is not None

    def test_ensure_index_resumes_interrupted_full_build(
        self, fake_git_repo, mock_embedder
    ):
        """Non --full build must continue build_full when meta has a checkpoint."""
        if fake_git_repo is None:
            pytest.skip("no git")
        (fake_git_repo / "b.py").write_text("def b():\n    return 2\n")
        subprocess.run(
            ["git", "add", "b.py"],
            cwd=fake_git_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "b"],
            cwd=fake_git_repo,
            capture_output=True,
            check=True,
        )
        _write_coderay_toml(fake_git_repo)
        indexer = Indexer(fake_git_repo, embedder=mock_embedder)
        indexer.build_full()

        idx_dir = (fake_git_repo / ".coderay").resolve()
        meta_path = idx_dir / "meta.json"
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        prefix = f"{fake_git_repo.name}/"
        m["state"] = "incomplete"
        m["current_run"] = {
            "paths_to_process": [f"{prefix}b.py", f"{prefix}hello.py"],
            "processed_count": 1,
            "error": None,
        }
        meta_path.write_text(json.dumps(m, indent=2), encoding="utf-8")

        indexer2 = Indexer(fake_git_repo, embedder=mock_embedder)
        result = indexer2.ensure_index()

        assert isinstance(result, IndexResult)
        final = indexer2._state.current_state
        assert final is not None
        assert final.state.value == "done"
        assert f"{prefix}hello.py" in indexer2._state.file_hashes
        assert f"{prefix}b.py" in indexer2._state.file_hashes
