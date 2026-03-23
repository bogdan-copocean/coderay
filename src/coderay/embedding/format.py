from __future__ import annotations

from coderay.core.models import Chunk


def format_chunk_for_embedding(chunk: Chunk) -> str:
    """Build embedder input: path, symbol, then source text."""
    return f"{chunk.path}\n{chunk.symbol}\n{chunk.content}"
