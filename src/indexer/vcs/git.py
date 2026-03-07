"""
Git operations: run commands, discover files, determine what to index.

Encapsulates git subprocess and parsing so the rest of the codebase
stays git-agnostic.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Status codes we treat as "should (re-)index this file" (work tree or index changed).
STATUS_FOR_INDEX = frozenset(
    [
        " M",  # unstaged modification
        "M ",  # staged modification
        "A ",  # staged addition
        "??",  # untracked
        "AM",
        "MM",
        "MD",
        "AD",
        "R ",  # staged rename
        "RM",
        "RD",
        "C ",  # staged copy
        "CM",
        "CD",
        "UU",  # unmerged
        "AA",
        "DD",
        "AU",
        "UA",
        "DU",
        "UD",
    ]
)

# Dirs to exclude when discovering .py files without git
EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".index",
        "venv",
        ".venv",
        "node_modules",
        "__pycache__",
        ".tox",
        "dist",
        "build",
    }
)


def _parse_status_line(line: str) -> tuple[str, str] | None:
    """Parse one line of `git status --short --porcelain`. Returns (status_xy, path).

    The XY status is the raw 2-char code (e.g. ' M', 'M ', '??').
    We must NOT strip it -- ' M' (unstaged) and 'M ' (staged) are distinct.
    """
    if len(line) < 4:
        return None
    status_xy = line[:2]
    path_part = line[3:].strip()
    if " -> " in path_part:
        path_part = path_part.split(" -> ", 1)[1].strip()
    return (status_xy, path_part)


class Git:
    """
    Runs git commands in a repo and determines which files to index.

    Used for cache invalidation: discover Python files and diff against
    last indexed commit to get paths to add or remove. All paths
    are relative to repo_root unless noted.
    """

    def __init__(self, repo_root: str | Path = ".") -> None:
        """
        Initialize with the repository root.

        Args:
            repo_root: Path to the git repository root. Defaults to current directory.
        """
        self.repo_root = Path(repo_root)

    def run(self, *args: str) -> str:
        """
        Run git with the given arguments in the repo.

        Returns:
            Stripped stdout.

        Raises:
            RuntimeError: If git exits non-zero.
        """
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)}: {result.stderr or result.stdout}"
            )
        return (result.stdout or "").strip()

    def get_head_commit(self) -> str | None:
        """
        Return current HEAD commit hash.

        Returns:
            Commit hash string, or None if not a git repo or detached HEAD.
        """
        try:
            return self.run("rev-parse", "HEAD")
        except (RuntimeError, FileNotFoundError):
            return None

    def get_current_branch(self) -> str | None:
        """
        Return current branch name.

        Returns:
            Branch name (e.g. "main"), or None if detached HEAD or not a repo.
        """
        try:
            name = self.run("rev-parse", "--abbrev-ref", "HEAD")
            if name and name != "HEAD":
                return name
        except (RuntimeError, FileNotFoundError):
            pass
        return None

    def is_branch_switched(self, last_branch: str | None = None) -> bool:
        """
        Return True if the current branch differs from the last saved branch.

        Args:
            last_branch: Branch name from last index run (e.g. from meta).

        Returns:
            True if current branch is different and both are non-None.
        """
        current_branch = self.get_current_branch()
        return (
            current_branch is not None
            and last_branch is not None
            and current_branch != last_branch
        )

    def get_files_to_index(
        self, last_commit: str | None
    ) -> tuple[list[Path], list[str]]:
        """
        Compute paths to re-index and paths to remove from the index.

        Uses last_commit from meta for diff; adds uncommitted changes from status.

        Args:
            last_commit: Last indexed commit; if None, returns ([], []).

        Returns:
            Tuple of (paths to add/re-index as Paths, paths to remove).
        """
        from indexer.chunking.registry import get_supported_extensions

        supported = get_supported_extensions()

        def _is_supported(path: str) -> bool:
            from pathlib import PurePosixPath

            return PurePosixPath(path).suffix in supported

        to_add: set[str] = set()
        to_remove: set[str] = set()

        try:
            head = self.get_head_commit()
            if not head or last_commit is None:
                return [], []

            try:
                diff_out = self.run("diff", "--name-status", f"{last_commit}...HEAD")
                for line in diff_out.splitlines():
                    parts = line.split("\t")
                    if len(parts) < 2:
                        continue
                    status = parts[0].strip()
                    path = (
                        parts[-1].strip() if status in ("R", "C") else parts[1].strip()
                    )
                    if not _is_supported(path):
                        continue
                    if status in ("A", "M", "R", "C"):
                        to_add.add(path)
                    elif status == "D":
                        to_remove.add(path)
            except RuntimeError:
                pass

            try:
                status_out = self.run("status", "--short", "--porcelain")
                for line in status_out.splitlines():
                    parsed = _parse_status_line(line)
                    if not parsed:
                        continue
                    s, path = parsed
                    if not _is_supported(path):
                        continue
                    if s in STATUS_FOR_INDEX:
                        to_add.add(path)
            except RuntimeError:
                pass

        except Exception as e:
            logger.warning("Git sync failed: %s", e)
            return [], []

        add_paths = [self.repo_root / p for p in sorted(to_add)]
        remove_paths = sorted(to_remove)
        return add_paths, remove_paths

    def discover_python_files(self) -> list[Path]:
        """List all Python files. Alias for discover_files(extensions={'.py'})."""
        return self.discover_files(extensions={".py"})

    def discover_files(
        self,
        extensions: set[str] | None = None,
    ) -> list[Path]:
        """
        List all source files under the repo matching the given extensions.

        Uses ``git ls-files`` when possible; otherwise rglob with exclusions.
        If extensions is None, uses all supported extensions from the registry.

        Returns:
            Sorted list of absolute Paths.
        """
        if extensions is None:
            from indexer.chunking.registry import get_supported_extensions

            extensions = get_supported_extensions()

        if (self.repo_root / ".git").exists():
            try:
                globs = [f"*{ext}" for ext in extensions]
                out = self.run("ls-files", *globs)
                if out:
                    lines = [p.strip() for p in out.splitlines() if p.strip()]
                    return sorted(self.repo_root / p for p in lines)
            except (RuntimeError, FileNotFoundError):
                pass

        result: list[Path] = []
        for f in self.repo_root.iterdir():
            if f.is_dir():
                if f.name in EXCLUDE_DIRS:
                    continue
                result.extend(self._rglob_filtered(f, extensions))
            elif f.suffix in extensions:
                result.append(f)
        return sorted(result)

    def _rglob_filtered(self, directory: Path, extensions: set[str]) -> list[Path]:
        found: list[Path] = []
        for f in directory.rglob("*"):
            if any(part in EXCLUDE_DIRS for part in f.parts):
                continue
            if f.is_file() and f.suffix in extensions:
                found.append(f)
        return found
