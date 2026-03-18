from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from coderay.core.config import get_config

META_FILENAME = "meta.json"
FILE_HASHES_FILENAME = "file_hashes.json"


class MetaState(str, Enum):
    """Indexer run state."""

    IN_PROGRESS = "in_progress"
    DONE = "done"
    ERRORED = "errored"
    INCOMPLETE = "incomplete"


@dataclass
class CurrentRun:
    """Resume info for current run."""

    paths_to_process: list[str] = field(default_factory=list)
    processed_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class IndexMeta:
    """Immutable meta.json snapshot."""

    state: MetaState
    started_at: float
    last_commit: str
    branch: str
    indexed_at: float
    current_run: CurrentRun
    error: str | None = None

    def is_in_progress(self):
        """Return True if in progress."""
        return self.state == MetaState.IN_PROGRESS

    def is_incomplete(self):
        """Return True if previous run did not finish."""
        return self.state == MetaState.INCOMPLETE


class StateMachine:
    """Manage index metadata and file hashes on disk."""

    def __init__(self) -> None:
        """Initialize from config."""
        self._index_dir = Path(get_config().index.path)
        self._meta_path = self._index_dir / META_FILENAME
        self._file_hashes_path = self._index_dir / FILE_HASHES_FILENAME
        self._current_state: IndexMeta | None = self._load_meta()
        self._file_hashes: dict[str, str] = self._load_file_hashes()

    @property
    def index_dir(self) -> Path:
        """Return index dir."""
        return self._index_dir

    @property
    def meta_path(self) -> Path:
        """Return meta.json path."""
        return self._meta_path

    @property
    def current_state(self) -> IndexMeta | None:
        """Return current meta; None if missing/invalid."""
        return self._current_state

    @current_state.setter
    def current_state(self, value: IndexMeta) -> None:
        self._current_state = value

    @property
    def file_hashes(self) -> dict[str, str]:
        """Return path -> hash mapping."""
        return self._file_hashes

    @file_hashes.setter
    def file_hashes(self, value: dict[str, str]) -> None:
        self._file_hashes = value

    def _load_meta(self) -> IndexMeta | None:
        """Load meta from disk; None if missing/invalid."""
        if not self._meta_path.exists():
            return None
        try:
            data = json.loads(self._meta_path.read_text())
            data["state"] = MetaState(data["state"])
            cr = data.get("current_run") or {}
            data["current_run"] = CurrentRun(
                paths_to_process=cr.get("paths_to_process") or [],
                processed_count=int(cr.get("processed_count") or 0),
                error=cr.get("error"),
            )
            return IndexMeta(**data)
        except Exception:
            return None

    def _load_file_hashes(self) -> dict[str, str]:
        """Load file hashes; {} if missing/invalid."""
        if not self._file_hashes_path.exists():
            return {}
        try:
            data = json.loads(self._file_hashes_path.read_text())
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}

    @property
    def is_in_progress(self) -> bool:
        """True if state is in_progress or incomplete."""
        if self._current_state is None:
            return False
        return (
            self._current_state.is_in_progress() or self._current_state.is_incomplete()
        )

    @property
    def has_partial_progress(self) -> bool:
        """Return True if run has paths and processed count > 0."""
        if self._current_state is None:
            return False
        run = self._current_state.current_run
        return bool(run.paths_to_process and run.processed_count > 0)

    def set_incomplete(self) -> None:
        """Mark run as incomplete."""
        if self._current_state is None or not self.is_in_progress:
            return
        data = asdict(self._current_state)
        data["state"] = MetaState.INCOMPLETE
        data["current_run"] = asdict(self._current_state.current_run)
        self._current_state = IndexMeta(
            state=data["state"],
            started_at=data["started_at"],
            last_commit=data["last_commit"],
            branch=data["branch"],
            indexed_at=data["indexed_at"],
            current_run=CurrentRun(**data["current_run"]),
        )
        self._save_meta()

    def set_errored(self, exc: str) -> None:
        if self._current_state is None:
            return
        data = asdict(self._current_state)
        current_run = asdict(self._current_state.current_run)
        self._current_state = IndexMeta(
            state=MetaState.ERRORED,
            error=exc,
            started_at=data["started_at"],
            last_commit=data["last_commit"],
            branch=data["branch"],
            indexed_at=data["indexed_at"],
            current_run=CurrentRun(
                paths_to_process=current_run["paths_to_process"],
                processed_count=current_run["processed_count"],
                error=exc,
            ),
        )
        self._save_meta()

    def start(self, branch: str | None, last_commit: str | None) -> None:
        """Start new indexing run."""
        now = time.time()
        self._current_state = IndexMeta(
            state=MetaState.IN_PROGRESS,
            started_at=now,
            last_commit=last_commit or "",
            branch=branch or "",
            indexed_at=now,
            current_run=CurrentRun(),
        )
        self._save_meta()

    def save_progress(
        self,
        full_rel_paths: list[str],
        processed_count: int,
    ) -> None:
        """Save resume checkpoint."""
        if self._current_state is None or not self.is_in_progress:
            return
        run = CurrentRun(
            paths_to_process=full_rel_paths,
            processed_count=processed_count,
        )
        self._current_state = IndexMeta(
            state=self._current_state.state,
            started_at=self._current_state.started_at,
            last_commit=self._current_state.last_commit,
            branch=self._current_state.branch,
            indexed_at=self._current_state.indexed_at,
            current_run=run,
        )
        self._save_meta()

    def finish(
        self,
        last_commit: str | None = None,
        branch: str | None = None,
    ) -> None:
        """Mark the current run as done and persist state."""
        self._save_file_hashes()
        if self._current_state is None:
            return
        commit = (
            last_commit if last_commit is not None else self._current_state.last_commit
        )
        br = branch if branch is not None else self._current_state.branch
        self._current_state = IndexMeta(
            state=MetaState.DONE,
            started_at=self._current_state.started_at,
            last_commit=commit,
            branch=br,
            indexed_at=time.time(),
            current_run=CurrentRun(),
        )
        self._save_meta()

    def _save_meta(self) -> None:
        """Write state to meta.json."""
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self._current_state)
        data["state"] = self._current_state.state.value
        self._meta_path.write_text(json.dumps(data, indent=2))

    def _save_file_hashes(self) -> None:
        """Write hashes to file_hashes.json."""
        self._file_hashes_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_hashes_path.write_text(
            json.dumps(self._file_hashes, indent=0, sort_keys=True)
        )
