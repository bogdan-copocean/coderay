"""Tests for indexer.vcs.git."""

from coderay.vcs.git import Git, _parse_status_line, load_gitignore


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
    def test_init(self, tmp_path):
        g = Git(tmp_path)
        assert g.repo_root == tmp_path

    def test_head_commit_non_repo(self, tmp_path):
        g = Git(tmp_path)
        assert g.get_head_commit() is None

    def test_current_branch_non_repo(self, tmp_path):
        g = Git(tmp_path)
        assert g.get_current_branch() is None

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
