"""Tests for indexer.vcs.git."""

import pytest

from indexer.vcs.git import STATUS_FOR_INDEX, Git, _parse_status_line


class TestParseStatusLine:
    def test_modified_unstaged(self):
        result = _parse_status_line(" M src/foo.py")
        assert result == (" M", "src/foo.py")

    def test_modified_staged(self):
        result = _parse_status_line("M  src/foo.py")
        assert result == ("M ", "src/foo.py")

    def test_untracked(self):
        result = _parse_status_line("?? new.py")
        assert result == ("??", "new.py")

    def test_rename(self):
        result = _parse_status_line("R  old.py -> new.py")
        assert result == ("R ", "new.py")

    def test_short_line_returns_none(self):
        assert _parse_status_line("??") is None

    def test_preserves_space_in_status(self):
        r1 = _parse_status_line(" M file.py")
        r2 = _parse_status_line("M  file.py")
        assert r1[0] != r2[0]


class TestStatusForIndex:
    def test_contains_unstaged_mod(self):
        assert " M" in STATUS_FOR_INDEX

    def test_contains_staged_mod(self):
        assert "M " in STATUS_FOR_INDEX

    def test_contains_untracked(self):
        assert "??" in STATUS_FOR_INDEX


class TestGit:
    def test_init(self, tmp_path):
        g = Git(tmp_path)
        assert g.repo_root == tmp_path

    def test_head_commit_non_repo(self, tmp_path):
        g = Git(tmp_path)
        assert g.get_head_commit() is None

    def test_current_branch_non_repo(self, tmp_path):
        g = Git(tmp_path)
        assert g.get_current_branch() is None

    def test_discover_python_files_fallback(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "b.pyc").write_text("y")
        g = Git(tmp_path)
        files = g.discover_python_files()
        paths_str = [str(f) for f in files]
        assert any("a.py" in p for p in paths_str)

    def test_get_files_to_index_no_commit(self, tmp_path):
        g = Git(tmp_path)
        add, remove = g.get_files_to_index(last_commit=None)
        assert add == []
        assert remove == []
