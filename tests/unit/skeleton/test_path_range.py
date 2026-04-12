"""Tests for skeleton path and file line range parsing."""

from __future__ import annotations

import pytest

from coderay.skeleton.path_range import parse_file_line_range, parse_skeleton_file_arg


@pytest.mark.parametrize(
    "s,path,expected",
    [
        ("foo.py", "foo.py", None),
        ("foo.py:10-20", "foo.py", (10, 20)),
        ("a:b:c.py:1-2", "a:b:c.py", (1, 2)),
    ],
)
def test_parse_skeleton_file_arg(s: str, path: str, expected):
    """Parse path with optional trailing file line range."""
    p, r = parse_skeleton_file_arg(s)
    assert p == path
    assert r == expected


@pytest.mark.parametrize(
    "s",
    ["foo.py:20-10", ":1-2"],
)
def test_parse_skeleton_file_arg_invalid(s: str):
    """Reject invalid file line range suffix."""
    with pytest.raises(ValueError):
        parse_skeleton_file_arg(s)


def test_parse_skeleton_file_arg_skips_suffix_when_disabled():
    """Without parse_suffix, treat path literally (full file)."""
    p, r = parse_skeleton_file_arg("foo.py:10-20", parse_suffix=False)
    assert p == "foo.py:10-20"
    assert r is None


def test_parse_file_line_range_ok():
    """Parse START-END string."""
    assert parse_file_line_range("3-40") == (3, 40)


def test_parse_file_line_range_invalid_order():
    """Reject end before start."""
    with pytest.raises(ValueError):
        parse_file_line_range("5-1")
