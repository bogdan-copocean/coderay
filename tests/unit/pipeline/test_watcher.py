"""Tests for indexer.pipeline.watcher."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from watchdog.events import (
    DirCreatedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)

from coderay.core.index_workspace import IndexWorkspace, resolve_index_workspace
from coderay.pipeline.watcher import FileWatcher, _DebouncedHandler

# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Return minimal repo directory."""
    r = tmp_path / "repo"
    r.mkdir()
    return r


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    """Return index directory (outside repo)."""
    d = tmp_path / ".coderay"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def repo_with_config(
    repo: Path,
    index_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Point config cache at repo so get_config(repo) matches tests."""
    from coderay.core.config import _reset_config_for_testing, config_for_repo

    monkeypatch.chdir(repo)
    cfg = config_for_repo(
        repo,
        {
            "index": {"path": str(index_dir), "exclude_patterns": []},
            "watcher": {"debounce": 2},
        },
    )
    _reset_config_for_testing(cfg)
    return repo


@pytest.fixture
def workspace(repo_with_config: Path) -> IndexWorkspace:
    """Resolved workspace for FileWatcher tests."""
    from coderay.core.config import get_config

    return resolve_index_workspace(repo_with_config, get_config(repo_with_config))


@pytest.fixture
def batch_log() -> list[tuple[set[str], set[str]]]:
    """Collect (changed, removed) batches for assertions."""
    return []


@pytest.fixture
def handler(
    repo: Path,
    index_dir: Path,
    batch_log: list,
    monkeypatch: pytest.MonkeyPatch,
) -> _DebouncedHandler:
    """Return handler with 0.1s debounce."""
    from coderay.core.config import _reset_config_for_testing, config_for_repo

    cfg = config_for_repo(
        repo,
        {
            "index": {"path": str(index_dir), "exclude_patterns": []},
            "watcher": {"debounce": 2},
        },
    )
    _reset_config_for_testing(cfg)
    monkeypatch.chdir(repo)
    ws = resolve_index_workspace(repo, cfg)
    return _DebouncedHandler(
        workspace=ws,
        debounce_seconds=0.1,
        on_batch=lambda c, r: batch_log.append((set(c), set(r))),
    )


# ── _DebouncedHandler filtering ──────────────────────────────────────


class TestHandlerFiltering:
    def test_ignores_directories(self, handler: _DebouncedHandler, repo: Path) -> None:
        handler.on_event(DirCreatedEvent(str(repo / "pkg")))
        assert handler.pending_count == 0

    def test_accepts_in_scope_file_regardless_of_suffix(
        self, handler: _DebouncedHandler, repo: Path
    ) -> None:
        handler.on_event(FileCreatedEvent(str(repo / "readme.md")))
        assert handler.pending_count == 1

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
        batch_log: list,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from coderay.core.config import _reset_config_for_testing, config_for_repo

        (repo / ".gitignore").write_text("generated/\n")
        cfg = config_for_repo(
            repo,
            {
                "index": {"path": str(index_dir), "exclude_patterns": []},
                "watcher": {"debounce": 2},
            },
        )
        _reset_config_for_testing(cfg)
        monkeypatch.chdir(repo)
        ws = resolve_index_workspace(repo, cfg)
        h = _DebouncedHandler(
            workspace=ws,
            debounce_seconds=0.1,
            on_batch=lambda c, r: batch_log.append((c, r)),
        )
        (repo / "generated").mkdir(exist_ok=True)
        h.on_event(FileCreatedEvent(str(repo / "generated" / "auto.py")))
        assert h.pending_count == 0

    def test_ignores_index_exclude_patterns(
        self,
        repo: Path,
        index_dir: Path,
        batch_log: list,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """index.exclude_patterns filters events (same rules as indexing)."""
        from coderay.core.config import _reset_config_for_testing, config_for_repo

        cfg = config_for_repo(
            repo,
            {
                "index": {
                    "path": str(index_dir),
                    "exclude_patterns": ["tmp_*.py"],
                },
                "watcher": {"debounce": 2},
            },
        )
        _reset_config_for_testing(cfg)
        monkeypatch.chdir(repo)
        ws = resolve_index_workspace(repo, cfg)
        h = _DebouncedHandler(
            workspace=ws,
            debounce_seconds=0.1,
            on_batch=lambda c, r: batch_log.append((c, r)),
        )
        h.on_event(FileCreatedEvent(str(repo / "tmp_scratch.py")))
        assert h.pending_count == 0

    def test_gitignore_filters_pycache(
        self,
        repo: Path,
        index_dir: Path,
        batch_log: list,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """__pycache__ is not hardcoded — it's filtered via .gitignore."""
        from coderay.core.config import _reset_config_for_testing, config_for_repo

        (repo / ".gitignore").write_text("__pycache__/\n")
        cfg = config_for_repo(
            repo,
            {
                "index": {"path": str(index_dir), "exclude_patterns": []},
                "watcher": {"debounce": 2},
            },
        )
        _reset_config_for_testing(cfg)
        monkeypatch.chdir(repo)
        ws = resolve_index_workspace(repo, cfg)
        h = _DebouncedHandler(
            workspace=ws,
            debounce_seconds=0.1,
            on_batch=lambda c, r: batch_log.append((c, r)),
        )
        (repo / "__pycache__").mkdir(exist_ok=True)
        h.on_event(FileCreatedEvent(str(repo / "__pycache__" / "side_effect.py")))
        assert h.pending_count == 0

    def test_accepts_in_scope_source_file(
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


# ── _DebouncedHandler debounce + flush ─────────────────────────────


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
        assert changed == {"repo/a.py"}
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
        assert changed == {"repo/a.py", "repo/b.py"}

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


# ── _DebouncedHandler batching ─────────────────────────────────────


class TestDebouncedHandlerBatching:
    def test_batch_accumulates_multiple_events(
        self,
        repo: Path,
        index_dir: Path,
        batch_log: list,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from coderay.core.config import _reset_config_for_testing, config_for_repo

        cfg = config_for_repo(
            repo,
            {
                "index": {"path": str(index_dir), "exclude_patterns": []},
                "watcher": {"debounce": 2},
            },
        )
        _reset_config_for_testing(cfg)
        monkeypatch.chdir(repo)
        ws = resolve_index_workspace(repo, cfg)
        h = _DebouncedHandler(
            workspace=ws,
            debounce_seconds=0.1,
            on_batch=lambda c, r: batch_log.append((set(c), set(r))),
        )
        for i in range(5):
            h.on_event(FileModifiedEvent(str(repo / f"f{i}.py")))
        h.flush_now()
        assert len(batch_log) == 1
        changed, _ = batch_log[0]
        assert len(changed) == 5


# ── FileWatcher lifecycle ───────────────────────────────────────────


class TestFileWatcher:
    def test_start_stop_lifecycle(
        self, workspace: IndexWorkspace, repo_with_config: Path
    ) -> None:
        calls: list[tuple] = []
        watcher = FileWatcher(
            workspace,
            debounce_seconds=2.0,
            on_batch=lambda c, r: calls.append((c, r)),
            use_polling=True,
        )
        watcher.start()
        assert watcher.update_count == 0
        watcher.stop()

    def test_detects_new_file(
        self, workspace: IndexWorkspace, repo_with_config: Path
    ) -> None:
        calls: list[tuple] = []

        def record(c: set[str], r: set[str]) -> None:
            calls.append((set(c), set(r)))

        watcher = FileWatcher(
            workspace,
            debounce_seconds=2.0,
            on_batch=record,
            use_polling=True,
        )
        watcher.start()
        try:
            (repo_with_config / "new_file.py").write_text("x = 1\n")
            time.sleep(2.0)
        finally:
            watcher.stop()

        assert len(calls) >= 1
        all_changed = set()
        for c, _ in calls:
            all_changed |= c
        assert "repo/new_file.py" in all_changed

    def test_respects_gitignore(
        self, repo_with_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Resolve workspace after .gitignore exists so gitignore_spec matches disk."""
        from coderay.core.config import get_config

        monkeypatch.chdir(repo_with_config)
        (repo_with_config / ".gitignore").write_text("scratch/\n")
        (repo_with_config / "scratch").mkdir()
        ws = resolve_index_workspace(repo_with_config, get_config(repo_with_config))

        calls: list[tuple] = []
        watcher = FileWatcher(
            ws,
            debounce_seconds=2.0,
            on_batch=lambda c, r: calls.append((c, r)),
            use_polling=True,
        )
        watcher.start()
        try:
            (repo_with_config / "scratch" / "temp.py").write_text("x = 1\n")
            time.sleep(2.0)
        finally:
            watcher.stop()

        assert len(calls) == 0
