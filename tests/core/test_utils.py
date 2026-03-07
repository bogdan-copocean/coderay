"""Tests for indexer.core.utils."""

from coderay.core.utils import files_with_changed_content, hash_content, read_from_path


class TestHashContent:
    def test_deterministic(self):
        assert hash_content("hello") == hash_content("hello")

    def test_different_inputs(self):
        assert hash_content("a") != hash_content("b")


class TestReadFromPath:
    def test_reads_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello")
        assert read_from_path(f) == "hello"


class TestFilesWithChangedContent:
    def test_detects_new(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        changed = files_with_changed_content(repo=tmp_path, paths=[f], file_hashes={})
        assert len(changed) == 1

    def test_unchanged(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        h = hash_content("x")
        changed = files_with_changed_content(
            repo=tmp_path, paths=[f], file_hashes={"a.py": h}
        )
        assert len(changed) == 0
