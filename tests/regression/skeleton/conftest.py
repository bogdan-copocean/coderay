"""Skeleton test fixtures for canonical concepts."""

from __future__ import annotations

from pathlib import Path

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_CANONICAL_PY = Path(__file__).with_name("canonical_concepts.py")
_CANONICAL_TS = Path(__file__).with_name("canonical_concepts.ts")


def load_skeleton_fixture(filename: str, *, canonical: str) -> str:
    """Return golden skeleton text with resolved absolute path (path:line-line headers)."""
    raw = (_FIXTURES / filename).read_text(encoding="utf-8")
    path = (_CANONICAL_PY if canonical == "py" else _CANONICAL_TS).resolve()
    return raw.replace("__CANONICAL_PATH__", str(path))


EXPECTED_UNKNOWN_SYMBOL_PREFIX = (
    """# Symbol '{symbol}' not found. Available symbols: """
)


# Aspirational bodies for xfail tests (closure symbol filter not implemented yet).
EXPECTED_PY_CANONICAL_SYMBOL_WRAPPER = """def wrapper(*args: Any, **kwargs: Any) -> T:
    \"\"\"Log the call and forward to the wrapped function.\"\"\"
    ..."""


EXPECTED_TS_SYMBOL_WRAPPER = (
    """        (value: string): string => `${prefix}:${value}`
            ..."""
).rstrip("\n")
