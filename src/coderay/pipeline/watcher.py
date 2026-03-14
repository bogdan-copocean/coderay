from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pathspec
from watchdog.events import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
    FileSystemEvent,
    FileSystemMovedEvent,
)
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from coderay.parsing.languages import get_supported_extensions
from coderay.vcs.git import load_gitignore

logger = logging.getLogger(__name__)


class _DebouncedHandler:
    """Accumulates filesystem events and flushes after a quiet window."""

    def __init__(
        self,
        repo_root: Path,
        index_dir: Path,
        gitignore_spec: pathspec.PathSpec,
        supported_extensions: set[str],
        debounce_seconds: float,
        branch_switch_threshold: int,
        extra_exclude: list[str],
        on_batch: Callable[[set[str], set[str]], None],
    ) -> None:
        """Initialize the debounced event handler."""
        self._repo_root = repo_root
        self._index_dir = index_dir
        self._gitignore = gitignore_spec
        self._extensions = supported_extensions
        self._debounce = debounce_seconds
        self._threshold = branch_switch_threshold
        self._on_batch = on_batch

        extra_spec = pathspec.PathSpec.from_lines("gitignore", extra_exclude)
        self._extra_spec = extra_spec

        self._lock = threading.Lock()
        self._changed: set[str] = set()
        self._removed: set[str] = set()
        self._timer: threading.Timer | None = None

    # -- public (called from watchdog observer thread) -----------------

    def on_event(self, event: FileSystemEvent) -> None:
        """Handle a single filesystem event from watchdog."""
        if event.is_directory:
            return

        paths = self._event_paths(event)
        for abs_path in paths:
            rel = self._relative(abs_path)
            if rel is None or not self._should_index(rel, abs_path):
                continue

            with self._lock:
                if event.event_type == EVENT_TYPE_DELETED:
                    self._removed.add(rel)
                    self._changed.discard(rel)
                elif event.event_type == EVENT_TYPE_MOVED:
                    assert isinstance(event, FileSystemMovedEvent)
                    old_rel = self._relative(event.src_path)
                    if old_rel:
                        self._removed.add(old_rel)
                        self._changed.discard(old_rel)
                    self._changed.add(rel)
                    self._removed.discard(rel)
                else:
                    self._changed.add(rel)
                    self._removed.discard(rel)

            self._reset_timer()

    def flush_now(self) -> None:
        """Force-flush any pending events (used during shutdown)."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._flush()

    @property
    def pending_count(self) -> int:
        """Number of accumulated events not yet flushed."""
        with self._lock:
            return len(self._changed) + len(self._removed)

    # -- internal ------------------------------------------------------

    def _event_paths(self, event: FileSystemEvent) -> list[str]:
        """Extract relevant absolute path(s) from an event."""
        if isinstance(event, FileSystemMovedEvent):
            return [event.dest_path]
        return [event.src_path]

    def _relative(self, abs_path: str) -> str | None:
        """Convert an absolute path to a repo-relative string, or None."""
        try:
            return str(Path(abs_path).relative_to(self._repo_root))
        except ValueError:
            return None

    def _should_index(self, rel_path: str, abs_path: str) -> bool:
        """Return True if the path is indexable (right extension, not ignored)."""
        parts = Path(rel_path).parts
        if ".git" in parts:
            return False

        try:
            Path(abs_path).relative_to(self._index_dir)
            return False
        except ValueError:
            pass

        if Path(abs_path).suffix not in self._extensions:
            return False

        if self._gitignore.match_file(rel_path):
            return False

        if self._extra_spec.match_file(rel_path):
            return False

        return True

    def _reset_timer(self) -> None:
        """Cancel existing timer and start a new debounce window."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        """Drain accumulated paths and invoke the batch callback."""
        with self._lock:
            changed = self._changed.copy()
            removed = self._removed.copy()
            self._changed.clear()
            self._removed.clear()
            self._timer = None

        if not changed and not removed:
            return

        total = len(changed) + len(removed)
        if total >= self._threshold:
            logger.info(
                "Branch switch detected (%d files); delegating to full sync",
                total,
            )

        try:
            self._on_batch(changed, removed)
        except Exception:
            logger.exception("Batch update failed")


class FileWatcher:
    """Watches a repository for changes and triggers index updates."""

    def __init__(
        self,
        repo_root: Path,
        index_dir: Path,
        on_batch: Callable[[set[str], set[str]], None] | None = None,
        *,
        use_polling: bool = False,
    ) -> None:
        """Initialize the file watcher from the application config."""
        from coderay.core.config import get_config

        self._repo_root = repo_root.resolve()
        self._index_dir = index_dir.resolve()
        self._config = get_config()
        self._on_batch = on_batch
        self._use_polling = use_polling

        watch_cfg = self._config.watcher
        self._debounce = float(watch_cfg.debounce)
        self._threshold = int(watch_cfg.branch_switch_threshold)
        self._extra_exclude = list(watch_cfg.exclude_patterns or [])

        self._observer: Observer | PollingObserver | None = None
        self._handler: _DebouncedHandler | None = None
        self._update_count = 0

    @property
    def update_count(self) -> int:
        """Number of batch updates executed since start."""
        return self._update_count

    def start(self) -> None:
        """Start the filesystem observer (non-blocking)."""
        gitignore_spec = load_gitignore(self._repo_root)
        extensions = get_supported_extensions()

        batch_fn = self._on_batch or self._default_batch
        self._handler = _DebouncedHandler(
            repo_root=self._repo_root,
            index_dir=self._index_dir,
            gitignore_spec=gitignore_spec,
            supported_extensions=extensions,
            debounce_seconds=self._debounce,
            branch_switch_threshold=self._threshold,
            extra_exclude=self._extra_exclude,
            on_batch=batch_fn,
        )

        adapter = _WatchdogAdapter(self._handler)
        if self._use_polling:
            self._observer = PollingObserver(timeout=1)
        else:
            self._observer = Observer()

        self._observer.schedule(adapter, str(self._repo_root), recursive=True)
        self._observer.daemon = True

        try:
            self._observer.start()
        except SystemError:
            logger.warning("Native observer failed; falling back to polling")
            self._observer = PollingObserver(timeout=1)
            self._observer.schedule(adapter, str(self._repo_root), recursive=True)
            self._observer.daemon = True
            self._observer.start()

        logger.info(
            "Watching %s (debounce=%.1fs, extensions=%d, observer=%s)",
            self._repo_root,
            self._debounce,
            len(extensions),
            type(self._observer).__name__,
        )

    def stop(self) -> None:
        """Stop the observer and flush remaining events."""
        if self._handler is not None:
            self._handler.flush_now()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
        logger.info("Watcher stopped (%d updates total)", self._update_count)

    def wait(self, timeout: float | None = None) -> None:
        """Block until the observer exits or timeout elapses."""
        if self._observer is not None:
            self._observer.join(timeout=timeout)

    def _default_batch(self, changed: set[str], removed: set[str]) -> None:
        """Default callback: acquire lock and run Indexer.update_paths."""
        from coderay.core.lock import acquire_indexer_lock
        from coderay.pipeline.indexer import Indexer

        total = len(changed) + len(removed)
        t0 = time.time()

        try:
            with acquire_indexer_lock(self._index_dir, timeout=30):
                indexer = Indexer(self._repo_root)
                if total >= self._threshold:
                    result = indexer.update_incremental()
                else:
                    result = indexer.update_paths(
                        changed=sorted(changed),
                        removed=sorted(removed),
                    )
            elapsed = time.time() - t0
            self._update_count += 1
            logger.info(
                "Update #%d: %s (%.2fs) [%d changed, %d removed]",
                self._update_count,
                result,
                elapsed,
                len(changed),
                len(removed),
            )
        except Exception:
            logger.exception("Failed to update index")


class _WatchdogAdapter:
    """Bridges watchdog's event handler protocol to our ``_DebouncedHandler``."""

    def __init__(self, handler: _DebouncedHandler) -> None:
        self._handler = handler

    def dispatch(self, event: FileSystemEvent) -> None:
        """Forward relevant events to the debounced handler."""
        if event.event_type in (
            EVENT_TYPE_CREATED,
            EVENT_TYPE_MODIFIED,
            EVENT_TYPE_DELETED,
            EVENT_TYPE_MOVED,
        ):
            self._handler.on_event(event)
