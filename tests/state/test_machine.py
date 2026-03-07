"""Tests for indexer.state.machine."""

import json

from coderay.state.machine import (
    FILE_HASHES_FILENAME,
    META_FILENAME,
    CurrentRun,
    IndexMeta,
    MetaState,
    StateMachine,
)


class TestMetaState:
    def test_values(self):
        assert MetaState.IN_PROGRESS.value == "in_progress"
        assert MetaState.DONE.value == "done"
        assert MetaState.ERRORED.value == "errored"
        assert MetaState.INCOMPLETE.value == "incomplete"


class TestCurrentRun:
    def test_defaults(self):
        run = CurrentRun()
        assert run.paths_to_process == []
        assert run.processed_count == 0
        assert run.error is None

    def test_with_values(self):
        run = CurrentRun(
            paths_to_process=["a.py", "b.py"],
            processed_count=1,
            error="oops",
        )
        assert run.paths_to_process == ["a.py", "b.py"]
        assert run.processed_count == 1
        assert run.error == "oops"


class TestIndexMeta:
    def test_is_in_progress(self):
        meta = IndexMeta(
            state=MetaState.IN_PROGRESS,
            started_at=0.0,
            last_commit="abc",
            branch="main",
            indexed_at=0.0,
            current_run=CurrentRun(),
        )
        assert meta.is_in_progress() is True

    def test_is_in_progress_false_when_done(self):
        meta = IndexMeta(
            state=MetaState.DONE,
            started_at=0.0,
            last_commit="abc",
            branch="main",
            indexed_at=0.0,
            current_run=CurrentRun(),
        )
        assert meta.is_in_progress() is False

    def test_is_incomplete(self):
        meta = IndexMeta(
            state=MetaState.INCOMPLETE,
            started_at=0.0,
            last_commit="abc",
            branch="main",
            indexed_at=0.0,
            current_run=CurrentRun(),
        )
        assert meta.is_incomplete() is True


class TestStateMachine:
    def test_init_empty_dir(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        assert sm.index_dir == tmp_index_dir
        assert sm.meta_path == tmp_index_dir / META_FILENAME
        assert sm.current_state is None
        assert sm.file_hashes == {}
        assert sm.is_in_progress is False
        assert sm.has_partial_progress is False

    def test_start_sets_in_progress(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        assert sm.current_state is not None
        assert sm.current_state.state == MetaState.IN_PROGRESS
        assert sm.current_state.branch == "main"
        assert sm.current_state.last_commit == "abc123"
        assert sm.is_in_progress is True

    def test_finish_sets_done(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.finish()
        assert sm.current_state is not None
        assert sm.current_state.state == MetaState.DONE
        assert sm.is_in_progress is False

    def test_finish_with_overrides(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.finish(last_commit="def456", branch="feature")
        assert sm.current_state.last_commit == "def456"
        assert sm.current_state.branch == "feature"

    def test_set_errored(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.set_errored("Something went wrong")
        assert sm.current_state.state == MetaState.ERRORED
        assert sm.current_state.error == "Something went wrong"
        assert sm.current_state.current_run.error == "Something went wrong"

    def test_set_errored_noop_when_no_state(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.set_errored("oops")
        assert sm.current_state is None

    def test_set_incomplete(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.set_incomplete()
        assert sm.current_state.state == MetaState.INCOMPLETE
        assert sm.is_in_progress is True

    def test_set_incomplete_noop_when_done(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.finish()
        sm.set_incomplete()
        assert sm.current_state.state == MetaState.DONE

    def test_save_progress(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.save_progress(full_rel_paths=["a.py", "b.py"], processed_count=1)
        assert sm.current_state.current_run.paths_to_process == ["a.py", "b.py"]
        assert sm.current_state.current_run.processed_count == 1
        assert sm.has_partial_progress is True

    def test_save_progress_noop_when_not_in_progress(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.save_progress(full_rel_paths=["a.py"], processed_count=1)
        assert sm.current_state is None

    def test_has_partial_progress_false_when_no_paths(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.save_progress(full_rel_paths=[], processed_count=0)
        assert sm.has_partial_progress is False

    def test_has_partial_progress_false_when_zero_processed(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.save_progress(full_rel_paths=["a.py"], processed_count=0)
        assert sm.has_partial_progress is False


class TestMetaPersistence:
    def test_meta_json_persisted_on_start(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        meta_path = tmp_index_dir / META_FILENAME
        assert meta_path.exists()
        data = json.loads(meta_path.read_text())
        assert data["state"] == "in_progress"
        assert data["branch"] == "main"
        assert data["last_commit"] == "abc123"

    def test_meta_loaded_on_init(self, tmp_index_dir):
        sm1 = StateMachine(tmp_index_dir)
        sm1.start(branch="main", last_commit="abc123")
        sm2 = StateMachine(tmp_index_dir)
        assert sm2.current_state is not None
        assert sm2.current_state.state == MetaState.IN_PROGRESS
        assert sm2.current_state.branch == "main"

    def test_meta_loaded_after_finish(self, tmp_index_dir):
        sm1 = StateMachine(tmp_index_dir)
        sm1.start(branch="main", last_commit="abc123")
        sm1.finish()
        sm2 = StateMachine(tmp_index_dir)
        assert sm2.current_state.state == MetaState.DONE

    def test_save_progress_persisted(self, tmp_index_dir):
        sm1 = StateMachine(tmp_index_dir)
        sm1.start(branch="main", last_commit="abc123")
        sm1.save_progress(full_rel_paths=["a.py", "b.py"], processed_count=1)
        sm2 = StateMachine(tmp_index_dir)
        assert sm2.current_state.current_run.paths_to_process == ["a.py", "b.py"]
        assert sm2.current_state.current_run.processed_count == 1


class TestFileHashesPersistence:
    def test_file_hashes_saved_on_finish(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.start(branch="main", last_commit="abc123")
        sm.file_hashes = {"a.py": "hash1", "b.py": "hash2"}
        sm.finish()
        hashes_path = tmp_index_dir / FILE_HASHES_FILENAME
        assert hashes_path.exists()
        data = json.loads(hashes_path.read_text())
        assert data == {"a.py": "hash1", "b.py": "hash2"}

    def test_file_hashes_loaded_on_init(self, tmp_index_dir):
        sm1 = StateMachine(tmp_index_dir)
        sm1.start(branch="main", last_commit="abc123")
        sm1.file_hashes = {"a.py": "hash1"}
        sm1.finish()
        sm2 = StateMachine(tmp_index_dir)
        assert sm2.file_hashes == {"a.py": "hash1"}

    def test_file_hashes_empty_when_missing(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        assert sm.file_hashes == {}

    def test_file_hashes_setter(self, tmp_index_dir):
        sm = StateMachine(tmp_index_dir)
        sm.file_hashes = {"x.py": "h1"}
        assert sm.file_hashes == {"x.py": "h1"}
