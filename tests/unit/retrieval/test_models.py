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

    @pytest.mark.parametrize(
        "line_count,max_lines,expected_truncated",
        [
            (30, 60, False),
            (60, 60, False),
            (100, 60, True),
            (200, None, False),
        ],
    )
    def test_truncation_behavior(self, line_count, max_lines, expected_truncated):
        content = "\n".join(f"line {i}" for i in range(line_count))
        result = SearchResult.from_raw(_make_row(content=content), max_lines=max_lines)
        if expected_truncated:
            assert result.truncated is True
            assert len(result.content.split("\n")) == (
                60 if max_lines == 60 else DEFAULT_MAX_CONTENT_LINES
            )
        else:
            assert result.content == content
            assert result.truncated is False

    def test_default_max_lines_truncates_when_exceeded(self):
        lines = [f"line {i}" for i in range(DEFAULT_MAX_CONTENT_LINES + 20)]
        content = "\n".join(lines)
        result = SearchResult.from_raw(_make_row(content=content))
        assert len(result.content.split("\n")) == DEFAULT_MAX_CONTENT_LINES
        assert result.truncated is True


class TestSearchResultToDict:
    """Tests for SearchResult.to_dict serialization."""

    def test_to_dict_has_required_keys(self):
        result = SearchResult.from_raw(_make_row(content="x"))
        d = result.to_dict()
        assert set(d.keys()) >= {
            "path",
            "start_line",
            "end_line",
            "symbol",
            "content",
            "score",
            "relevance",
            "search_mode",
        }


class TestContains:
    """Tests for SearchResult.contains()."""

    @pytest.mark.parametrize(
        "path_a,range_a,path_b,range_b,expected",
        [
            ("a.py", (1, 10), "a.py", (1, 10), True),
            ("a.py", (1, 50), "a.py", (10, 30), True),
            ("a.py", (10, 30), "a.py", (1, 50), False),
            ("a.py", (1, 100), "b.py", (10, 30), False),
        ],
    )
    def test_contains_invariant(self, path_a, range_a, path_b, range_b, expected):
        a = SearchResult(path_a, range_a[0], range_a[1], "f", "", score=0.9)
        b = SearchResult(path_b, range_b[0], range_b[1], "g", "", score=0.8)
        assert a.contains(b) == expected

    def test_partial_overlap_neither_contains(self):
        a = SearchResult("a.py", 1, 20, "f", "", score=0.9)
        b = SearchResult("a.py", 15, 35, "g", "", score=0.8)
        assert a.contains(b) is False
        assert b.contains(a) is False


class TestIsTestPath:
    """Tests for the is_test_path helper."""

    @pytest.mark.parametrize(
        "path,expected",
        [
            # Python conventions
            ("src/tests/test_foo.py", True),
            ("test_foo.py", True),
            ("foo_test.py", True),
            ("tests/conftest.py", True),
            # JavaScript / TypeScript conventions
            ("src/utils/utils.spec.js", True),
            ("src/components/Button.spec.tsx", True),
            ("src/__tests__/auth.ts", True),
            # Not test paths
            ("src/coderay/retrieval/search.py", False),
            ("src/coderay/__init__.py", False),
            ("src/services/user.service.ts", False),
        ],
    )
    def test_is_test_path(self, path, expected):
        assert is_test_path(path) == expected
