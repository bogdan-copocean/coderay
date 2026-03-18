from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DEFAULT_MAX_CONTENT_LINES: int = 60

Relevance = Literal["high", "medium", "low"]

_TEST_PATH_PATTERNS: tuple[str, ...] = (
    "/tests/",
    "/test/",
    "/test_",
    "_test.py",
    "/conftest.py",
    "/conftest_",
)


def is_test_path(path: str) -> bool:
    """Return True if *path* looks like a test file."""
    normalised = f"/{path}"
    return any(p in normalised for p in _TEST_PATH_PATTERNS)


@dataclass(frozen=True)
class SearchResult:
    """A single search hit with optional content truncation."""

    path: str
    start_line: int
    end_line: int
    symbol: str
    content: str
    score: float = 0.0
    truncated: bool = False
    relevance: Relevance = "high"
    search_mode: str = "vector"

    @classmethod
    def from_raw(
        cls,
        row: dict,
        *,
        max_lines: int | None = DEFAULT_MAX_CONTENT_LINES,
    ) -> SearchResult:
        """Build from a raw dict returned by the storage layer.

        Args:
            row: Dict with keys path, start_line, end_line, symbol,
                content, score, and search_mode.
            max_lines: Truncate content beyond this many lines.
                None disables truncation.
        """
        content: str = row.get("content", "")
        truncated = False

        if max_lines is not None:
            lines = content.split("\n")
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines])
                truncated = True

        return cls(
            path=row["path"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            symbol=row["symbol"],
            content=content,
            score=float(row.get("score", 0.0)),
            truncated=truncated,
            search_mode=row.get("search_mode", "vector"),
        )

    def contains(self, other: SearchResult) -> bool:
        """Return True if this result's span fully encloses *other*.

        Both results must be in the same file.
        """
        return (
            self.path == other.path
            and self.start_line <= other.start_line
            and self.end_line >= other.end_line
        )

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict for the MCP response."""
        d: dict = {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "symbol": self.symbol,
            "content": self.content,
            "score": self.score,
            "relevance": self.relevance,
            "search_mode": self.search_mode,
        }
        if self.truncated:
            d["truncated"] = True
        return d
