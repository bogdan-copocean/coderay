"""Tests for embedding input formatting."""

from coderay.core.models import Chunk
from coderay.embedding.format import format_chunk_for_embedding


def test_format_includes_path_and_symbol():
    """Formatted text carries path and symbol for retrieval."""
    c = Chunk(
        path="src/x.py",
        start_line=1,
        end_line=2,
        symbol="foo",
        content="def foo():\n    pass",
    )
    s = format_chunk_for_embedding(c)
    assert s.startswith("src/x.py\nfoo\n")
    assert "def foo()" in s
