from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from watchdog.events import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
    FileSystemEvent,
    FileSystemEventHandler,
    FileSystemMovedEvent,
)
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from coderay.core.index_workspace import should_index_event
from coderay.core.timing import timed_phase

logger = logging.getLogger(__name__)


class _DebouncedHandler:
    """Accumulate filesystem events; flush after quiet window."""

    def __init__(
        self,
        workspace: object,
        debounce_seconds: float,
        on_batch: Callable[[set[str], set[str]], None],
    ) -> None:
        """Initialize debounced handler."""
        from coderay.core.index_workspace import IndexWorkspace

        if not isinstance(workspace, IndexWorkspace):
            raise TypeError("workspace must be IndexWorkspace")
        self._workspace = workspace
        self._debounce = debounce_seconds
        self._on_batch = on_batch

        self._lock = threading.Lock()
        self._changed: set[str] = set()
        self._removed: set[str] = set()
        self._timer: threading.Timer | None = None

    # -- public (called from watchdog observer thread) -----------------

    def on_event(self, event: FileSystemEvent) -> None:
        """Handle filesystem event."""
        if event.is_directory:
            return

        paths = self._event_paths(event)
        for abs_path in paths:
            key = self._logical_key(abs_path)
            if key is None:
                continue

            with self._lock:
                if event.event_type == EVENT_TYPE_DELETED:
                    self._removed.add(key)
                    self._changed.discard(key)
                elif event.event_type == EVENT_TYPE_MOVED:
                    assert isinstance(event, FileSystemMovedEvent)
                    old_key = self._logical_key(str(event.src_path))
                    if old_key:
                        self._removed.add(old_key)
                        self._changed.discard(old_key)
                    self._changed.add(key)
                    self._removed.discard(key)
                else:
                    self._changed.add(key)
                    self._removed.discard(key)

            self._reset_timer()

    def flush_now(self) -> None:
        """Force-flush pending events."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._flush()

    @property
    def pending_count(self) -> int:
        """Return count of unflushed events."""
        with self._lock:
            return len(self._changed) + len(self._removed)

    # -- internal ------------------------------------------------------

    def _event_paths(self, event: FileSystemEvent) -> list[str]:
        """Extract absolute path(s) from event."""
        if isinstance(event, FileSystemMovedEvent):
            return [str(event.dest_path)]
        return [str(event.src_path)]

    def _logical_key(self, abs_path: str) -> str | None:
        """Return logical index key if path is in index scope; else None."""
        key, _ = should_index_event(self._workspace, Path(abs_path))
        return key

    def _reset_timer(self) -> None:
        """Reset debounce timer."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        """Drain paths and invoke batch callback."""
        with self._lock:
            changed = self._changed.copy()
            removed = self._removed.copy()
            self._changed.clear()
            self._removed.clear()
            self._timer = None

        if not changed and not removed:
            return

        try:
            self._on_batch(changed, removed)
        except Exception:
            logger.exception("Batch update failed")


class FileWatcher:
    """Watch resolved index roots; trigger index updates."""

    def __init__(
        self,
        workspace: object,
        *,
        debounce_seconds: float = 2.0,
        on_batch: Callable[[set[str], set[str]], None] | None = None,
        use_polling: bool = False,
    ) -> None:
        """Attach to ``workspace.watch_directories()`` with debounced batches."""
        from coderay.core.index_workspace import IndexWorkspace

        if not isinstance(workspace, IndexWorkspace):
            raise TypeError("workspace must be IndexWorkspace")
        self._workspace = workspace
        self._debounce = float(debounce_seconds)
        self._on_batch = on_batch
        self._use_polling = use_polling

        self._observer: Observer | PollingObserver | None = None  # type: ignore[valid-type]
        self._handler: _DebouncedHandler | None = None
        self._update_count = 0

    @property
    def update_count(self) -> int:
        """Return batch update count."""
        return self._update_count

    def start(self) -> None:
        """Start filesystem observer (non-blocking)."""
        batch_fn = self._on_batch or self._default_batch
        self._handler = _DebouncedHandler(
            workspace=self._workspace,
            debounce_seconds=self._debounce,
            on_batch=batch_fn,
        )

        adapter = _WatchdogAdapter(self._handler)
        if self._use_polling:
            self._observer = PollingObserver(timeout=1)
        else:
            self._observer = Observer()

        self._observer.daemon = True
        watch_dirs = self._workspace.watch_directories()
        for wd in watch_dirs:
            self._observer.schedule(adapter, str(wd), recursive=True)

        try:
            self._observer.start()
        except SystemError:
            logger.warning("Native observer failed; falling back to polling")
            self._observer = PollingObserver(timeout=1)
            self._observer.daemon = True
            for wd in watch_dirs:
                self._observer.schedule(adapter, str(wd), recursive=True)
            self._observer.start()

        logger.info(
            "Watching %s (debounce=%.1fs, observer=%s)",
            ", ".join(str(w) for w in watch_dirs),
            self._debounce,
            type(self._observer).__name__,
        )

    def stop(self) -> None:
        """Stop observer and flush."""
        if self._handler is not None:
            self._handler.flush_now()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
        logger.info("Watcher stopped (%d updates total)", self._update_count)

    def wait(self, timeout: float | None = None) -> None:
        """Block until observer exits or timeout."""
        if self._observer is not None:
            self._observer.join(timeout=timeout)

    def _default_batch(self, changed: set[str], removed: set[str]) -> None:
        """Default callback: acquire lock, run update_incremental."""
        from coderay.core.lock import acquire_indexer_lock
        from coderay.pipeline.indexer import Indexer

        try:
            with (
                timed_phase("update", log=False) as tp,
                acquire_indexer_lock(self._workspace.index_dir, timeout=30),
            ):
                indexer = Indexer(self._workspace.config_repo_root)
                result = indexer.update_incremental()
            self._update_count += 1
            logger.info(
                "Update #%d: %s (%.2fs) [%d changed, %d removed]",
                self._update_count,
                result,
                tp.elapsed,
                len(changed),
                len(removed),
            )
        except Exception:
            logger.exception("Failed to update index")


class _WatchdogAdapter(FileSystemEventHandler):
    """Bridge watchdog events to _DebouncedHandler."""

    def __init__(self, handler: _DebouncedHandler) -> None:
        self._handler = handler

    def dispatch(self, event: FileSystemEvent) -> None:
        """Forward events to debounced handler."""
        if event.event_type in (
            EVENT_TYPE_CREATED,
            EVENT_TYPE_MODIFIED,
            EVENT_TYPE_DELETED,
            EVENT_TYPE_MOVED,
        ):
            self._handler.on_event(event)
