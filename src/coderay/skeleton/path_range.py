"""Parse file path with optional file line range suffix."""

from __future__ import annotations

import re

_SUFFIX = re.compile(r":(\d+)-(\d+)$")


def parse_skeleton_file_arg(
    path: str, *, parse_suffix: bool = True
) -> tuple[str, tuple[int, int] | None]:
    """Return filesystem path and optional file line range (1-based inclusive).

    If parse_suffix is False, return the path unchanged and no range (full file).
    """
    if not parse_suffix:
        return path, None
    m = _SUFFIX.search(path)
    if not m:
        return path, None
    start, end = int(m.group(1)), int(m.group(2))
    if end < start:
        raise ValueError("file line range end must be >= start")
    base = path[: m.start()]
    if not base:
        raise ValueError("empty path before file line range")
    return base, (start, end)


def parse_file_line_range(s: str) -> tuple[int, int]:
    """Parse START-END file line range (1-based inclusive)."""
    m = re.fullmatch(r"(\d+)-(\d+)", s.strip())
    if not m:
        raise ValueError("expected file line range START-END")
    start, end = int(m.group(1)), int(m.group(2))
    if end < start:
        raise ValueError("file line range end must be >= start")
    return start, end
