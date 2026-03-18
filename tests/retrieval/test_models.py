"""Tests for retrieval result models."""

import pytest

from coderay.retrieval.models import (
    DEFAULT_MAX_CONTENT_LINES,
    SearchResult,
    is_test_path,
)


def _make_row(
    content: str = "line\n" * 10,
    score: float = 0.85,
    search_mode: str = "vector",
) -> dict:
    return {
        "path": "src/app.py",
        "start_line": 1,
        "end_line": 10,
        "symbol": "foo",
        "content": content,
        "score": score,
        "search_mode": search_mode,
    }


class TestSearchResultFromRaw:
    """Tests for SearchResult.from_raw factory."""

    def test_basic_fields(self):
        row = _make_row(content="hello")
        result = SearchResult.from_raw(row)

        assert result.path == "src/app.py"
        assert result.start_line == 1
        assert result.end_line == 10
        assert result.symbol == "foo"
        assert result.content == "hello"
        assert result.score == 0.85
        assert result.truncated is False

    def test_score_from_row(self):
        row = _make_row(content="x", score=0.92)
        result = SearchResult.from_raw(row)
        assert result.score == 0.92

    def test_score_defaults_to_zero_when_missing(self):
        row = _make_row(content="x")
        del row["score"]
        result = SearchResult.from_raw(row)
        assert result.score == 0.0

    def test_search_mode_from_row(self):
        row = _make_row(content="x", search_mode="hybrid")
        result = SearchResult.from_raw(row)
        assert result.search_mode == "hybrid"

    def test_search_mode_defaults_to_vector(self):
        row = _make_row(content="x")
        del row["search_mode"]
        result = SearchResult.from_raw(row)
        assert result.search_mode == "vector"

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
            "relevance",
            "search_mode",
        }
        assert set(d.keys()) == expected

    def test_score_in_dict(self):
        result = SearchResult.from_raw(_make_row(content="x", score=0.77))
        d = result.to_dict()
        assert d["score"] == 0.77

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

    def test_relevance_defaults_to_high(self):
        result = SearchResult.from_raw(_make_row(score=0.5))
        d = result.to_dict()
        assert d["relevance"] == "high"

    def test_relevance_in_dict(self):
        result = SearchResult(
            path="a.py",
            start_line=1,
            end_line=10,
            symbol="foo",
            content="x",
            score=0.1,
            relevance="low",
        )
        d = result.to_dict()
        assert d["relevance"] == "low"

    def test_search_mode_in_dict(self):
        result = SearchResult.from_raw(
            _make_row(content="x", search_mode="hybrid")
        )
        d = result.to_dict()
        assert d["search_mode"] == "hybrid"


class TestContains:
    """Tests for SearchResult.contains()."""

    def test_same_range(self):
        a = SearchResult("a.py", 1, 10, "f", "", score=0.9)
        b = SearchResult("a.py", 1, 10, "g", "", score=0.8)
        assert a.contains(b) is True

    def test_outer_contains_inner(self):
        outer = SearchResult("a.py", 1, 50, "Cls", "", score=0.9)
        inner = SearchResult("a.py", 10, 30, "Cls.method", "", score=0.8)
        assert outer.contains(inner) is True
        assert inner.contains(outer) is False

    def test_different_files(self):
        a = SearchResult("a.py", 1, 100, "f", "", score=0.9)
        b = SearchResult("b.py", 10, 30, "g", "", score=0.8)
        assert a.contains(b) is False

    def test_partial_overlap(self):
        a = SearchResult("a.py", 1, 20, "f", "", score=0.9)
        b = SearchResult("a.py", 15, 35, "g", "", score=0.8)
        assert a.contains(b) is False
        assert b.contains(a) is False


class TestIsTestPath:
    """Tests for the is_test_path helper."""

    def test_test_directory(self):
        assert is_test_path("src/tests/test_foo.py") is True

    def test_test_prefix(self):
        assert is_test_path("test_foo.py") is True

    def test_test_suffix(self):
        assert is_test_path("foo_test.py") is True

    def test_conftest(self):
        assert is_test_path("tests/conftest.py") is True

    def test_production_file(self):
        assert is_test_path("src/coderay/retrieval/search.py") is False

    def test_init_file(self):
        assert is_test_path("src/coderay/__init__.py") is False
