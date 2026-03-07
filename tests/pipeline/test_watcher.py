"""Tests for indexer.pipeline.watcher."""

from __future__ import annotations

import time
from pathlib import Path

import pathspec
import pytest
from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)

from coderay.pipeline.watcher import (
    FileWatcher,
    _DebouncedHandler,
)
from coderay.vcs.git import load_gitignore

# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Minimal repo directory."""
    r = tmp_path / "repo"
    r.mkdir()
    return r


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    """Separate index directory (outside repo, like the real .index)."""
    d = tmp_path / ".index"
    d.mkdir()
    return d


@pytest.fixture
def empty_spec() -> pathspec.PathSpec:
    return pathspec.PathSpec.from_lines("gitignore", [])


@pytest.fixture
def python_extensions() -> set[str]:
    return {".py"}


@pytest.fixture
def batch_log() -> list[tuple[set[str], set[str]]]:
    """Collects (changed, removed) batches for assertions."""
    return []


@pytest.fixture
def handler(
    repo: Path,
    index_dir: Path,
    empty_spec: pathspec.PathSpec,
    python_extensions: set[str],
    batch_log: list,
) -> _DebouncedHandler:
    """Pre-wired handler with 0.1 s debounce for fast tests."""
    return _DebouncedHandler(
        repo_root=repo,
        index_dir=index_dir,
        gitignore_spec=empty_spec,
        supported_extensions=python_extensions,
        debounce_seconds=0.1,
        branch_switch_threshold=50,
        extra_exclude=[],
        on_batch=lambda c, r: batch_log.append((set(c), set(r))),
    )


# ── load_gitignore ───────────────────────────────────────────────────


class TestLoadGitignore:
    def test_missing_file_returns_empty_spec(self, tmp_path: Path) -> None:
        spec = load_gitignore(tmp_path)
        assert not spec.match_file("anything.py")

    def test_parses_patterns(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.log\nbuild/\n")
        spec = load_gitignore(tmp_path)
        assert spec.match_file("app.log")
        assert spec.match_file("build/out.js")
        assert not spec.match_file("src/main.py")


# ── _DebouncedHandler filtering ──────────────────────────────────────


class TestHandlerFiltering:
    def test_ignores_directories(self, handler: _DebouncedHandler, repo: Path) -> None:
        evt = FileCreatedEvent(str(repo / "pkg"))
        evt._is_directory = True
        handler.on_event(evt)
        assert handler.pending_count == 0

    def test_ignores_unsupported_extension(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        handler.on_event(FileCreatedEvent(str(repo / "readme.md")))
        assert handler.pending_count == 0

    def test_ignores_git_dir(self, handler: _DebouncedHandler, repo: Path) -> None:
        handler.on_event(FileModifiedEvent(str(repo / ".git" / "index")))
        assert handler.pending_count == 0

    def test_ignores_index_dir(
        self, handler: _DebouncedHandler, repo: Path, index_dir: Path
    ) -> None:
        handler.on_event(FileModifiedEvent(str(index_dir / "meta.json")))
        assert handler.pending_count == 0

    def test_ignores_gitignored_files(
        self,
        repo: Path,
        index_dir: Path,
        python_extensions: set[str],
        batch_log: list,
    ) -> None:
        spec = pathspec.PathSpec.from_lines("gitignore", ["generated/"])
        h = _DebouncedHandler(
            repo_root=repo,
            index_dir=index_dir,
            gitignore_spec=spec,
            supported_extensions=python_extensions,
            debounce_seconds=0.1,
            branch_switch_threshold=50,
            extra_exclude=[],
            on_batch=lambda c, r: batch_log.append((c, r)),
        )
        h.on_event(FileCreatedEvent(str(repo / "generated" / "auto.py")))
        assert h.pending_count == 0

    def test_ignores_extra_exclude_patterns(
        self,
        repo: Path,
        index_dir: Path,
        empty_spec: pathspec.PathSpec,
        python_extensions: set[str],
        batch_log: list,
    ) -> None:
        h = _DebouncedHandler(
            repo_root=repo,
            index_dir=index_dir,
            gitignore_spec=empty_spec,
            supported_extensions=python_extensions,
            debounce_seconds=0.1,
            branch_switch_threshold=50,
            extra_exclude=["tmp_*.py"],
            on_batch=lambda c, r: batch_log.append((c, r)),
        )
        h.on_event(FileCreatedEvent(str(repo / "tmp_scratch.py")))
        assert h.pending_count == 0

    def test_gitignore_filters_pycache(
        self,
        repo: Path,
        index_dir: Path,
        python_extensions: set[str],
        batch_log: list,
    ) -> None:
        """__pycache__ is not hardcoded — it's filtered via .gitignore."""
        spec = pathspec.PathSpec.from_lines("gitignore", ["__pycache__/"])
        h = _DebouncedHandler(
            repo_root=repo,
            index_dir=index_dir,
            gitignore_spec=spec,
            supported_extensions=python_extensions,
            debounce_seconds=0.1,
            branch_switch_threshold=50,
            extra_exclude=[],
            on_batch=lambda c, r: batch_log.append((c, r)),
        )
        h.on_event(FileCreatedEvent(str(repo / "__pycache__" / "mod.cpython-311.pyc")))
        assert h.pending_count == 0

    def test_accepts_valid_python_file(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        handler.on_event(FileCreatedEvent(str(repo / "app.py")))
        assert handler.pending_count == 1


# ── _DebouncedHandler event accumulation ─────────────────────────────


class TestHandlerAccumulation:
    def test_created_adds_to_changed(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        handler.on_event(FileCreatedEvent(str(repo / "a.py")))
        handler.on_event(FileCreatedEvent(str(repo / "b.py")))
        assert handler.pending_count == 2

    def test_modified_adds_to_changed(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        handler.on_event(FileModifiedEvent(str(repo / "a.py")))
        assert handler.pending_count == 1

    def test_deleted_adds_to_removed(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        handler.on_event(FileDeletedEvent(str(repo / "a.py")))
        assert handler.pending_count == 1

    def test_delete_after_create_keeps_only_removed(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        handler.on_event(FileCreatedEvent(str(repo / "a.py")))
        handler.on_event(FileDeletedEvent(str(repo / "a.py")))
        assert handler.pending_count == 1
        handler.flush_now()

    def test_create_after_delete_keeps_only_changed(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        handler.on_event(FileDeletedEvent(str(repo / "a.py")))
        handler.on_event(FileCreatedEvent(str(repo / "a.py")))
        assert handler.pending_count == 1

    def test_move_event_removes_old_and_adds_new(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        evt = FileMovedEvent(str(repo / "old.py"), str(repo / "new.py"))
        handler.on_event(evt)
        assert handler.pending_count == 2


# ── _DebouncedHandler debounce + flush ───────────────────────────────


class TestHandlerDebounce:
    def test_debounce_fires_after_quiet_window(
        self,
        handler: _DebouncedHandler,
        repo: Path,
        batch_log: list,
    ) -> None:
        handler.on_event(FileModifiedEvent(str(repo / "a.py")))
        time.sleep(0.3)
        assert len(batch_log) == 1
        changed, removed = batch_log[0]
        assert changed == {"a.py"}
        assert removed == set()

    def test_rapid_events_coalesce_into_one_batch(
        self,
        handler: _DebouncedHandler,
        repo: Path,
        batch_log: list,
    ) -> None:
        for i in range(5):
            handler.on_event(FileModifiedEvent(str(repo / f"f{i}.py")))
            time.sleep(0.02)
        time.sleep(0.3)
        assert len(batch_log) == 1
        changed, _ = batch_log[0]
        assert len(changed) == 5

    def test_debounce_resets_on_new_event(
        self,
        handler: _DebouncedHandler,
        repo: Path,
        batch_log: list,
    ) -> None:
        handler.on_event(FileModifiedEvent(str(repo / "a.py")))
        time.sleep(0.05)
        handler.on_event(FileModifiedEvent(str(repo / "b.py")))
        time.sleep(0.05)
        assert len(batch_log) == 0
        time.sleep(0.2)
        assert len(batch_log) == 1
        changed, _ = batch_log[0]
        assert changed == {"a.py", "b.py"}

    def test_flush_now_fires_immediately(
        self,
        handler: _DebouncedHandler,
        repo: Path,
        batch_log: list,
    ) -> None:
        handler.on_event(FileModifiedEvent(str(repo / "a.py")))
        handler.flush_now()
        assert len(batch_log) == 1

    def test_flush_now_noop_when_empty(
        self,
        handler: _DebouncedHandler,
        batch_log: list,
    ) -> None:
        handler.flush_now()
        assert len(batch_log) == 0


# ── _DebouncedHandler branch-switch detection ────────────────────────


class TestBranchSwitchDetection:
    def test_logs_branch_switch_when_threshold_exceeded(
        self,
        repo: Path,
        index_dir: Path,
        empty_spec: pathspec.PathSpec,
        python_extensions: set[str],
        batch_log: list,
    ) -> None:
        h = _DebouncedHandler(
            repo_root=repo,
            index_dir=index_dir,
            gitignore_spec=empty_spec,
            supported_extensions=python_extensions,
            debounce_seconds=0.1,
            branch_switch_threshold=3,
            extra_exclude=[],
            on_batch=lambda c, r: batch_log.append((set(c), set(r))),
        )
        for i in range(5):
            h.on_event(FileModifiedEvent(str(repo / f"f{i}.py")))
        h.flush_now()
        assert len(batch_log) == 1
        changed, _ = batch_log[0]
        assert len(changed) == 5


# ── FileWatcher lifecycle ────────────────────────────────────────────


class TestFileWatcher:
    def test_start_stop_lifecycle(self, repo: Path, tmp_path: Path) -> None:
        idx = tmp_path / ".index"
        idx.mkdir()
        calls: list[tuple] = []
        watcher = FileWatcher(
            repo,
            idx,
            config={"watch": {"debounce_seconds": 0.1}},
            on_batch=lambda c, r: calls.append((c, r)),
            use_polling=True,
        )
        watcher.start()
        assert watcher.update_count == 0
        watcher.stop()

    def test_detects_new_file(self, repo: Path, tmp_path: Path) -> None:
        idx = tmp_path / ".index"
        idx.mkdir()
        calls: list[tuple] = []

        def record(c: set[str], r: set[str]) -> None:
            calls.append((set(c), set(r)))

        watcher = FileWatcher(
            repo,
            idx,
            config={"watch": {"debounce_seconds": 0.15}},
            on_batch=record,
            use_polling=True,
        )
        watcher.start()
        try:
            (repo / "new_file.py").write_text("x = 1\n")
            time.sleep(2.0)
        finally:
            watcher.stop()

        assert len(calls) >= 1
        all_changed = set()
        for c, _ in calls:
            all_changed |= c
        assert "new_file.py" in all_changed

    def test_ignores_non_source_files(self, repo: Path, tmp_path: Path) -> None:
        idx = tmp_path / ".index"
        idx.mkdir()
        calls: list[tuple] = []
        watcher = FileWatcher(
            repo,
            idx,
            config={"watch": {"debounce_seconds": 0.1}},
            on_batch=lambda c, r: calls.append((c, r)),
            use_polling=True,
        )
        watcher.start()
        try:
            (repo / "notes.txt").write_text("hello\n")
            time.sleep(2.0)
        finally:
            watcher.stop()

        assert len(calls) == 0

    def test_respects_gitignore(self, repo: Path, tmp_path: Path) -> None:
        idx = tmp_path / ".index"
        idx.mkdir()
        (repo / ".gitignore").write_text("scratch/\n")
        (repo / "scratch").mkdir()

        calls: list[tuple] = []
        watcher = FileWatcher(
            repo,
            idx,
            config={"watch": {"debounce_seconds": 0.1}},
            on_batch=lambda c, r: calls.append((c, r)),
            use_polling=True,
        )
        watcher.start()
        try:
            (repo / "scratch" / "temp.py").write_text("x = 1\n")
            time.sleep(2.0)
        finally:
            watcher.stop()

        assert len(calls) == 0
