"""Tests for retrieval result models."""

import pytest

from coderay.retrieval.models import DEFAULT_MAX_CONTENT_LINES, SearchResult


def _make_row(
    content: str = "line\n" * 10,
    *,
    score: float = 0.85,
) -> dict:
    return {
        "path": "src/app.py",
        "start_line": 1,
        "end_line": 10,
        "symbol": "foo",
        "content": content,
        "score": score,
    }


class TestSearchResultFromRaw:
    """Tests for SearchResult.from_raw factory."""

    def test_basic_fields(self):
        row = _make_row(content="hello", score=0.9)
        result = SearchResult.from_raw(row)

        assert result.path == "src/app.py"
        assert result.start_line == 1
        assert result.end_line == 10
        assert result.symbol == "foo"
        assert result.content == "hello"
        assert result.score == 0.9
        assert result.truncated is False

    def test_no_truncation_when_under_limit(self):
        content = "\n".join(f"line {i}" for i in range(30))
        result = SearchResult.from_raw(_make_row(content=content), max_lines=60)

        assert result.content == content
        assert result.truncated is False

    def test_truncation_at_exact_limit(self):
        lines = [f"line {i}" for i in range(60)]
        content = "\n".join(lines)
        result = SearchResult.from_raw(_make_row(content=content), max_lines=60)

        assert result.content == content
        assert result.truncated is False

    def test_truncation_over_limit(self):
        lines = [f"line {i}" for i in range(100)]
        content = "\n".join(lines)
        result = SearchResult.from_raw(_make_row(content=content), max_lines=60)

        assert result.content == "\n".join(lines[:60])
        assert result.truncated is True

    def test_truncation_disabled_with_none(self):
        lines = [f"line {i}" for i in range(200)]
        content = "\n".join(lines)
        result = SearchResult.from_raw(_make_row(content=content), max_lines=None)

        assert result.content == content
        assert result.truncated is False

    def test_default_max_lines_applied(self):
        lines = [f"line {i}" for i in range(DEFAULT_MAX_CONTENT_LINES + 20)]
        content = "\n".join(lines)
        result = SearchResult.from_raw(_make_row(content=content))

        output_lines = result.content.split("\n")
        assert len(output_lines) == DEFAULT_MAX_CONTENT_LINES
        assert result.truncated is True

    def test_empty_content(self):
        result = SearchResult.from_raw(_make_row(content=""))

        assert result.content == ""
        assert result.truncated is False

    def test_missing_content_key_defaults_empty(self):
        row = _make_row()
        del row["content"]
        result = SearchResult.from_raw(row)

        assert result.content == ""

    def test_missing_score_defaults_zero(self):
        row = _make_row()
        del row["score"]
        result = SearchResult.from_raw(row)

        assert result.score == 0.0

    def test_extra_keys_ignored(self):
        row = _make_row()
        row["raw_score"] = 0.5
        row["vector"] = [0.1, 0.2]
        result = SearchResult.from_raw(row)

        assert result.path == "src/app.py"


class TestSearchResultToDict:
    """Tests for SearchResult.to_dict serialization."""

    def test_keys_present(self):
        result = SearchResult.from_raw(_make_row(content="x"))
        d = result.to_dict()

        expected = {
            "path",
            "start_line",
            "end_line",
            "symbol",
            "content",
            "score",
        }
        assert set(d.keys()) == expected

    def test_truncated_flag_included_when_true(self):
        lines = [f"line {i}" for i in range(100)]
        content = "\n".join(lines)
        result = SearchResult.from_raw(
            _make_row(content=content),
            max_lines=10,
        )
        d = result.to_dict()

        assert d["truncated"] is True

    def test_truncated_flag_absent_when_false(self):
        result = SearchResult.from_raw(_make_row(content="short"))
        d = result.to_dict()

        assert "truncated" not in d

    def test_frozen_dataclass(self):
        result = SearchResult.from_raw(_make_row())
        with pytest.raises(AttributeError):
            result.content = "mutated"  # type: ignore[misc]
