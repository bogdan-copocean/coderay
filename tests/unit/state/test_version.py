"""Tests for index schema versioning."""

import json

from coderay.state.version import (
    INDEX_SCHEMA_VERSION,
    check_index_version,
    read_index_version,
    write_index_version,
)


class TestWriteAndRead:
    def test_write_then_read(self, tmp_path):
        write_index_version(tmp_path)
        version = read_index_version(tmp_path)
        assert version == INDEX_SCHEMA_VERSION

    def test_read_missing_returns_none(self, tmp_path):
        assert read_index_version(tmp_path) is None

    def test_read_corrupt_returns_none(self, tmp_path):
        (tmp_path / "version.json").write_text("not json")
        assert read_index_version(tmp_path) is None

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b"
        write_index_version(nested)
        assert read_index_version(nested) == INDEX_SCHEMA_VERSION


class TestCheckIndexVersion:
    def test_no_file_no_warning(self, tmp_path, caplog):
        check_index_version(tmp_path)
        assert "mismatch" not in caplog.text

    def test_matching_version_no_warning(self, tmp_path, caplog):
        write_index_version(tmp_path)
        check_index_version(tmp_path)
        assert "mismatch" not in caplog.text

    def test_mismatched_version_warns(self, tmp_path, caplog):
        (tmp_path / "version.json").write_text(json.dumps({"schema_version": 999}))
        import logging

        with caplog.at_level(logging.WARNING):
            check_index_version(tmp_path)
        assert "mismatch" in caplog.text
