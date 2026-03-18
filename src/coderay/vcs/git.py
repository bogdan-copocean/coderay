from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pathspec

logger = logging.getLogger(__name__)


def load_gitignore(repo_root: Path) -> pathspec.PathSpec:
    """Parse .gitignore into PathSpec matcher."""
    gitignore = repo_root / ".gitignore"
    if not gitignore.is_file():
        return pathspec.PathSpec.from_lines("gitignore", [])
    try:
        lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        return pathspec.PathSpec.from_lines("gitignore", lines)
    except Exception:
        logger.warning("Failed to parse .gitignore; no patterns loaded")
        return pathspec.PathSpec.from_lines("gitignore", [])


def _parse_status_line(line: str) -> tuple[str, str] | None:
    """Parse one line of git status --short --porcelain."""
    if len(line) < 4:
        return None
    status_xy = line[:2]
    path_part = line[3:].strip()
    if " -> " in path_part:
        path_part = path_part.split(" -> ", 1)[1].strip()
    return (status_xy, path_part)


class Git:
    """Git operations for file discovery and change detection."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        """Initialize with repository root."""
        self.repo_root = Path(repo_root)

    def run(self, *args: str) -> str:
        """Run git command; return stripped stdout."""
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
        """Return HEAD commit hash; None if unavailable."""
        try:
            return self.run("rev-parse", "HEAD")
        except (RuntimeError, FileNotFoundError):
            return None

    def get_current_branch(self) -> str | None:
        """Return current branch; None if detached."""
        try:
            name = self.run("rev-parse", "--abbrev-ref", "HEAD")
            if name and name != "HEAD":
                return name
        except (RuntimeError, FileNotFoundError):
            pass
        return None

    def is_branch_switched(self, last_branch: str | None = None) -> bool:
        """Return True if current branch differs from last_branch."""
        current_branch = self.get_current_branch()
        return (
            current_branch is not None
            and last_branch is not None
            and current_branch != last_branch
        )

    def get_files_to_index(
        self, last_commit: str | None
    ) -> tuple[list[Path], list[str]]:
        """Return (paths_to_add, paths_to_remove) since last commit."""
        from coderay.parsing.languages import get_supported_extensions

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

            # 1. Committed changes since last indexed commit.
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
                    if status == "D":
                        to_remove.add(path)
                    else:
                        to_add.add(path)
            except RuntimeError:
                pass

            # 2. Uncommitted changes (working tree + staging area).
            #    Instead of matching against a status-code set, check
            #    the filesystem: if the file exists → re-index,
            #    otherwise → remove.
            try:
                status_out = self.run("status", "--short", "--porcelain")
                for line in status_out.splitlines():
                    parsed = _parse_status_line(line)
                    if not parsed:
                        continue
                    status_xy, path = parsed
                    if status_xy == "!!":
                        continue
                    if not _is_supported(path):
                        continue
                    if (self.repo_root / path).is_file():
                        to_add.add(path)
                    else:
                        to_remove.add(path)
            except RuntimeError:
                pass

        except Exception as e:
            logger.warning("Git sync failed: %s", e)
            return [], []

        add_paths = [self.repo_root / p for p in sorted(to_add)]
        remove_paths = sorted(to_remove)
        return add_paths, remove_paths

    def discover_python_files(self) -> list[Path]:
        """List Python files; alias for discover_files(extensions={'.py'})."""
        return self.discover_files(extensions={".py"})

    def discover_files(
        self,
        extensions: set[str] | None = None,
    ) -> list[Path]:
        """List source files matching extensions."""
        if extensions is None:
            from coderay.parsing.languages import get_supported_extensions

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

        # Fallback: rglob filtered through .gitignore.
        ignore = load_gitignore(self.repo_root)
        result: list[Path] = []
        for f in self.repo_root.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix not in extensions:
                continue
            rel = str(f.relative_to(self.repo_root))
            if ignore.match_file(rel):
                continue
            if ".git" in Path(rel).parts:
                continue
            result.append(f)
        return sorted(result)
