"""Tests for indexer.state.machine."""

import json

import pytest

from coderay.core.config import _reset_config_for_testing, config_for_repo
from coderay.state.machine import (
    FILE_HASHES_FILENAME,
    META_FILENAME,
    CheckoutIndexState,
    CurrentRun,
    IndexMeta,
    MetaState,
    StateMachine,
)


def _sources(
    commit: str = "abc123",
    branch: str = "main",
    *,
    alias: str = "proj",
    is_primary: bool = True,
) -> tuple[CheckoutIndexState, ...]:
    return (
        CheckoutIndexState(
            alias=alias, commit=commit, branch=branch, is_primary=is_primary
        ),
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
            indexed_at=0.0,
            current_run=CurrentRun(),
            sources=_sources(),
        )
        assert meta.is_in_progress() == expected_in_progress
        assert meta.is_incomplete() == expected_incomplete

    @pytest.mark.parametrize(
        "sources,expect_alias",
        [
            (
                (
                    CheckoutIndexState("a", "c1", "main", is_primary=True),
                    CheckoutIndexState("b", "c2", "dev", is_primary=False),
                ),
                "a",
            ),
            ((CheckoutIndexState("only", "c0", "x", is_primary=False),), "only"),
        ],
    )
    def test_primary_prefers_project_else_sole(
        self, sources: tuple[CheckoutIndexState, ...], expect_alias: str
    ) -> None:
        meta = IndexMeta(
            state=MetaState.DONE,
            started_at=0.0,
            indexed_at=0.0,
            current_run=CurrentRun(),
            sources=sources,
        )
        p = meta.primary()
        assert p is not None
        assert p.alias == expect_alias


class TestStateMachine:
    def test_init_empty_dir(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        assert sm.index_dir == tmp_index_dir
        assert sm.meta_path == tmp_index_dir / META_FILENAME
        assert sm.current_state is None
        assert sm.file_hashes == {}
        assert sm.is_in_progress is False
        assert sm.has_partial_progress is False

    def test_start_sets_in_progress(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        assert sm.current_state is not None
        assert sm.current_state.state == MetaState.IN_PROGRESS
        assert sm.current_state.sources[0].branch == "main"
        assert sm.current_state.sources[0].commit == "abc123"
        assert sm.is_in_progress is True

    def test_finish_sets_done(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        sm.finish()
        assert sm.current_state is not None
        assert sm.current_state.state == MetaState.DONE
        assert sm.is_in_progress is False

    def test_finish_with_overrides(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        sm.finish(sources=_sources(commit="def456", branch="feature"))
        assert sm.current_state.sources[0].commit == "def456"
        assert sm.current_state.sources[0].branch == "feature"

    def test_set_errored(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        sm.set_errored("Something went wrong")
        assert sm.current_state.state == MetaState.ERRORED
        assert sm.current_state.error == "Something went wrong"
        assert sm.current_state.current_run.error == "Something went wrong"

    def test_set_errored_noop_when_no_state(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.set_errored("oops")
        assert sm.current_state is None

    def test_set_incomplete(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        sm.set_incomplete()
        assert sm.current_state.state == MetaState.INCOMPLETE
        assert sm.is_in_progress is True

    def test_set_incomplete_noop_when_done(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        sm.finish()
        sm.set_incomplete()
        assert sm.current_state.state == MetaState.DONE

    def test_save_progress(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        sm.save_progress(full_rel_paths=["a.py", "b.py"], processed_count=1)
        assert sm.current_state.current_run.paths_to_process == ["a.py", "b.py"]
        assert sm.current_state.current_run.processed_count == 1
        assert sm.has_partial_progress is True

    def test_save_progress_noop_when_not_in_progress(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
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
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        sm.save_progress(full_rel_paths=paths, processed_count=processed_count)
        assert sm.has_partial_progress is expected


class TestMetaPersistence:
    def test_meta_json_persisted_on_start(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        meta_path = tmp_index_dir / META_FILENAME
        assert meta_path.exists()
        data = json.loads(meta_path.read_text())
        assert data["state"] == "in_progress"
        assert data["sources"][0]["branch"] == "main"
        assert data["sources"][0]["commit"] == "abc123"

    def test_meta_loaded_on_init(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm1 = StateMachine()
        sm1.start(sources=_sources())
        sm2 = StateMachine()
        assert sm2.current_state is not None
        assert sm2.current_state.state == MetaState.IN_PROGRESS
        assert sm2.current_state.sources[0].branch == "main"

    def test_meta_loaded_after_finish(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm1 = StateMachine()
        sm1.start(sources=_sources())
        sm1.finish()
        sm2 = StateMachine()
        assert sm2.current_state.state == MetaState.DONE

    def test_save_progress_persisted(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm1 = StateMachine()
        sm1.start(sources=_sources())
        sm1.save_progress(full_rel_paths=["a.py", "b.py"], processed_count=1)
        sm2 = StateMachine()
        assert sm2.current_state.current_run.paths_to_process == ["a.py", "b.py"]
        assert sm2.current_state.current_run.processed_count == 1

    def test_load_legacy_last_commit_only(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        meta_path = tmp_index_dir / META_FILENAME
        meta_path.write_text(
            json.dumps(
                {
                    "state": "done",
                    "started_at": 1.0,
                    "indexed_at": 2.0,
                    "current_run": {},
                    "last_commit": "deadbeef",
                    "branch": "main",
                }
            ),
            encoding="utf-8",
        )
        sm = StateMachine()
        assert sm.current_state is not None
        assert len(sm.current_state.sources) == 1
        assert sm.current_state.sources[0].alias == "r0"
        assert sm.current_state.sources[0].commit == "deadbeef"
        assert sm.current_state.sources[0].branch == "main"
        assert sm.current_state.sources[0].is_primary is True

    def test_load_legacy_root_commits(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        meta_path = tmp_index_dir / META_FILENAME
        meta_path.write_text(
            json.dumps(
                {
                    "state": "done",
                    "started_at": 1.0,
                    "indexed_at": 2.0,
                    "current_run": {},
                    "root_commits": {"r0": "aaa", "r1": "bbb"},
                    "root_branches": {"r0": "main", "r1": "dev"},
                }
            ),
            encoding="utf-8",
        )
        sm = StateMachine()
        by_alias = {s.alias: s for s in sm.current_state.sources}
        assert by_alias["r0"].commit == "aaa"
        assert by_alias["r1"].branch == "dev"


class TestFileHashesPersistence:
    def test_file_hashes_saved_on_finish(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm = StateMachine()
        sm.start(sources=_sources())
        sm.file_hashes = {"a.py": "hash1", "b.py": "hash2"}
        sm.finish()
        hashes_path = tmp_index_dir / FILE_HASHES_FILENAME
        assert hashes_path.exists()
        data = json.loads(hashes_path.read_text())
        assert data == {"a.py": "hash1", "b.py": "hash2"}

    def test_file_hashes_loaded_on_init(self, tmp_index_dir):
        cfg = config_for_repo(
            tmp_index_dir.parent, {"index": {"path": str(tmp_index_dir)}}
        )
        _reset_config_for_testing(cfg)
        sm1 = StateMachine()
        sm1.start(sources=_sources())
        sm1.file_hashes = {"a.py": "hash1"}
        sm1.finish()
        sm2 = StateMachine()
        assert sm2.file_hashes == {"a.py": "hash1"}
