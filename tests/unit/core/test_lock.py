"""Tests for indexer.core.lock."""

from coderay.core.lock import acquire_indexer_lock, lock_path


class TestLockPath:
    def test_returns_path(self, tmp_path):
        p = lock_path(tmp_path)
        assert p.name == ".indexer.lock"
        assert p.parent == tmp_path


class TestAcquireIndexerLock:
    def test_context_manager(self, tmp_path):
        with acquire_indexer_lock(tmp_path):
            assert (tmp_path / ".indexer.lock").exists()
