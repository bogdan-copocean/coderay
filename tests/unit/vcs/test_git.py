"""Tests for indexer.vcs.git."""

import pytest

from coderay.vcs.git import Git, _parse_status_line, load_gitignore


class TestParseStatusLine:
    @pytest.mark.parametrize(
        "line,expected",
        [
            (" M src/foo.py", (" M", "src/foo.py")),
            ("M  src/foo.py", ("M ", "src/foo.py")),
            ("?? new.py", ("??", "new.py")),
            ("R  old.py -> new.py", ("R ", "new.py")),
            ("??", None),
        ],
    )
    def test_parse_status_line(self, line, expected):
        assert _parse_status_line(line) == expected

    def test_preserves_space_in_status(self):
        r1 = _parse_status_line(" M file.py")
        r2 = _parse_status_line("M  file.py")
        assert r1[0] != r2[0]


class TestLoadGitignore:
    def test_missing_returns_empty(self, tmp_path):
        spec = load_gitignore(tmp_path)
        assert not spec.match_file("anything.py")

    def test_parses_patterns(self, tmp_path):
        (tmp_path / ".gitignore").write_text("*.log\nbuild/\n__pycache__/\n")
        spec = load_gitignore(tmp_path)
        assert spec.match_file("app.log")
        assert spec.match_file("build/out.js")
        assert spec.match_file("__pycache__/mod.pyc")
        assert not spec.match_file("src/main.py")


class TestGit:
    @pytest.mark.parametrize("method", ["get_head_commit", "get_current_branch"])
    def test_non_repo_returns_none(self, tmp_path, method):
        g = Git(tmp_path)
        assert getattr(g, method)() is None

    def test_discover_files_fallback_uses_gitignore(self, tmp_path):
        """Non-git fallback filters via .gitignore, not a hardcoded set."""
        (tmp_path / ".gitignore").write_text("__pycache__/\nvenv/\n")
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "b.pyc").write_text("y")
        (tmp_path / "venv").mkdir()
        (tmp_path / "venv" / "lib.py").write_text("z")
        g = Git(tmp_path)
        files = g.discover_files(extensions={".py"})
        names = {f.name for f in files}
        assert "a.py" in names
        assert "lib.py" not in names

    def test_discover_files_fallback_no_gitignore(self, tmp_path):
        """Without .gitignore, all files are discovered (except .git)."""
        (tmp_path / "a.py").write_text("x")
        sub = tmp_path / "mydir"
        sub.mkdir()
        (sub / "b.py").write_text("y")
        g = Git(tmp_path)
        files = g.discover_files(extensions={".py"})
        names = {f.name for f in files}
        assert names == {"a.py", "b.py"}

    def test_get_files_to_index_no_commit(self, tmp_path):
        g = Git(tmp_path)
        add, remove = g.get_files_to_index(last_commit=None)
        assert add == []
        assert remove == []
