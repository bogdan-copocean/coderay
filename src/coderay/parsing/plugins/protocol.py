"""Protocols for language plugins (chunker, skeleton)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from coderay.core.models import Chunk
    from coderay.parsing.base import ParserContext


class ChunkerProtocol(Protocol):
    """Chunk a file into semantic units (functions, classes, preamble)."""

    def chunk(self, ctx: "ParserContext") -> list["Chunk"]:
        """Return chunks for the parsed file."""
        ...


class SkeletonProtocol(Protocol):
    """Extract skeleton (signatures, docstrings, no bodies)."""

    def extract(
        self,
        ctx: "ParserContext",
        *,
        include_imports: bool = True,
        symbol: str | None = None,
    ) -> str:
        """Return skeleton text."""
        ...
