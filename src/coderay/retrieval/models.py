from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_CONTENT_LINES: int = 60


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
                and content.
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
        )

    def to_dict(self, *, top_score: float | None = None) -> dict:
        """Serialize to a JSON-compatible dict for the MCP response.

        Args:
            top_score: When provided, a ``low_confidence`` flag is added
                to the output.  Results scoring below 30 % of the top
                score are flagged.
        """
        d: dict = {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "symbol": self.symbol,
            "content": self.content,
            "score": self.score,
        }
        if self.truncated:
            d["truncated"] = True
        if top_score is not None:
            threshold = top_score * 0.3
            d["low_confidence"] = self.score < threshold
        return d
