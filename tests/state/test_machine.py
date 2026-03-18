"""Tests for indexer.state.machine."""

import json
from pathlib import Path

import pytest

from coderay.core.config import Config, IndexConfig, _reset_config_for_testing
from coderay.state.machine import (
    FILE_HASHES_FILENAME,
    META_FILENAME,
    CurrentRun,
    IndexMeta,
    MetaState,
    StateMachine,
)


class TestIndexMeta:
    @pytest.mark.parametrize(
        "state,expected_in_progress,expected_incomplete",
        [
            (MetaState.IN_PROGRESS, True, False),
            (MetaState.DONE, False, False),
            (MetaState.INCOMPLETE, False, True),
        ],
    )
    def test_state_predicates(self, state, expected_in_progress, expected_incomplete):
        meta = IndexMeta(
            state=state,
            started_at=0.0,
            last_commit="abc",
            branch="main",
            indexed_at=0.0,
            current_run=CurrentRun(),
        )
        assert meta.is_in_progress() == expected_in_progress
        assert meta.is_incomplete() == expected_incomplete


class TestStateMachine:
    def test_init_empty_dir(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        assert sm.index_dir == tmp_index_dir
        assert sm.meta_path == tmp_index_dir / META_FILENAME
        assert sm.current_state is None
        assert sm.file_hashes == {}
        assert sm.is_in_progress is False
        assert sm.has_partial_progress is False

    def test_start_sets_in_progress(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        assert sm.current_state is not None
        assert sm.current_state.state == MetaState.IN_PROGRESS
        assert sm.current_state.branch == "main"
        assert sm.current_state.last_commit == "abc123"
        assert sm.is_in_progress is True

    def test_finish_sets_done(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        sm.finish()
        assert sm.current_state is not None
        assert sm.current_state.state == MetaState.DONE
        assert sm.is_in_progress is False

    def test_finish_with_overrides(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        sm.finish(last_commit="def456", branch="feature")
        assert sm.current_state.last_commit == "def456"
        assert sm.current_state.branch == "feature"

    def test_set_errored(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        sm.set_errored("Something went wrong")
        assert sm.current_state.state == MetaState.ERRORED
        assert sm.current_state.error == "Something went wrong"
        assert sm.current_state.current_run.error == "Something went wrong"

    def test_set_errored_noop_when_no_state(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.set_errored("oops")
        assert sm.current_state is None

    def test_set_incomplete(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        sm.set_incomplete()
        assert sm.current_state.state == MetaState.INCOMPLETE
        assert sm.is_in_progress is True

    def test_set_incomplete_noop_when_done(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        sm.finish()
        sm.set_incomplete()
        assert sm.current_state.state == MetaState.DONE

    def test_save_progress(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        sm.save_progress(full_rel_paths=["a.py", "b.py"], processed_count=1)
        assert sm.current_state.current_run.paths_to_process == ["a.py", "b.py"]
        assert sm.current_state.current_run.processed_count == 1
        assert sm.has_partial_progress is True

    def test_save_progress_noop_when_not_in_progress(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.save_progress(full_rel_paths=["a.py"], processed_count=1)
        assert sm.current_state is None

    @pytest.mark.parametrize(
        "paths,processed_count,expected",
        [
            ([], 0, False),
            (["a.py"], 0, False),
            (["a.py", "b.py"], 1, True),
        ],
    )
    def test_has_partial_progress(
        self, tmp_index_dir, paths, processed_count, expected
    ):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        sm.save_progress(full_rel_paths=paths, processed_count=processed_count)
        assert sm.has_partial_progress is expected


class TestMetaPersistence:
    def test_meta_json_persisted_on_start(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        meta_path = tmp_index_dir / META_FILENAME
        assert meta_path.exists()
        data = json.loads(meta_path.read_text())
        assert data["state"] == "in_progress"
        assert data["branch"] == "main"
        assert data["last_commit"] == "abc123"

    def test_meta_loaded_on_init(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm1 = StateMachine()
        sm1.start(branch="main", last_commit="abc123")
        sm2 = StateMachine()
        assert sm2.current_state is not None
        assert sm2.current_state.state == MetaState.IN_PROGRESS
        assert sm2.current_state.branch == "main"

    def test_meta_loaded_after_finish(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm1 = StateMachine()
        sm1.start(branch="main", last_commit="abc123")
        sm1.finish()
        sm2 = StateMachine()
        assert sm2.current_state.state == MetaState.DONE

    def test_save_progress_persisted(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm1 = StateMachine()
        sm1.start(branch="main", last_commit="abc123")
        sm1.save_progress(full_rel_paths=["a.py", "b.py"], processed_count=1)
        sm2 = StateMachine()
        assert sm2.current_state.current_run.paths_to_process == ["a.py", "b.py"]
        assert sm2.current_state.current_run.processed_count == 1


class TestFileHashesPersistence:
    def test_file_hashes_saved_on_finish(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(branch="main", last_commit="abc123")
        sm.file_hashes = {"a.py": "hash1", "b.py": "hash2"}
        sm.finish()
        hashes_path = tmp_index_dir / FILE_HASHES_FILENAME
        assert hashes_path.exists()
        data = json.loads(hashes_path.read_text())
        assert data == {"a.py": "hash1", "b.py": "hash2"}

    def test_file_hashes_loaded_on_init(self, tmp_index_dir):
        cfg = Config(index=IndexConfig(path=str(tmp_index_dir)))
        _reset_config_for_testing(cfg)
        sm1 = StateMachine()
        sm1.start(branch="main", last_commit="abc123")
        sm1.file_hashes = {"a.py": "hash1"}
        sm1.finish()
        sm2 = StateMachine()
        assert sm2.file_hashes == {"a.py": "hash1"}
