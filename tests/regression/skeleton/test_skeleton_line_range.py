"""Skeleton symbol line range column and file line range filter."""

from __future__ import annotations

import re
from pathlib import Path

from coderay.skeleton.extractor import extract_skeleton

CANONICAL = Path(__file__).with_name("canonical_concepts.py")
_REF_LINE = re.compile(r".+:\d+-\d+$")


def test_symbol_line_range_path_line_before_def():
    """Absolute path line (with symbol line range) precedes each declaration."""
    path, content = str(CANONICAL), CANONICAL.read_text(encoding="utf-8")
    sk = extract_skeleton(path, content, include_imports=False)
    lines = sk.splitlines()
    i = next(i for i, ln in enumerate(lines) if "def top_level_helper" in ln)
    assert _REF_LINE.fullmatch(lines[i - 1].strip())
    assert str(CANONICAL.resolve()) in lines[i - 1]
    assert ":27-29" in lines[i - 1]
    assert not lines[i].lstrip().startswith("27-")
    doc = next(ln for ln in lines if "Return the sum of two integers" in ln)
    assert str(CANONICAL.resolve()) not in doc


def test_file_line_range_empty_message():
    """No declarations fully inside the range yields file line range hint."""
    path, content = str(CANONICAL), CANONICAL.read_text(encoding="utf-8")
    out = extract_skeleton(
        path,
        content,
        line_range=(99998, 99999),
    )
    assert "file line range 99998-99999" in out


def test_file_line_range_keeps_only_fully_inside_window():
    """Emit only declarations whose span lies entirely in the file line range."""
    path, content = str(CANONICAL), CANONICAL.read_text(encoding="utf-8")
    out = extract_skeleton(
        path,
        content,
        include_imports=False,
        line_range=(27, 35),
    )
    assert "def top_level_helper" in out
    assert "async def async_helper" in out
    assert "class BaseService" not in out
