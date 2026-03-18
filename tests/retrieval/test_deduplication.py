"""Tests for containment-based deduplication of search results."""

from coderay.retrieval.search import deduplicate_by_containment


def _r(path: str, start: int, end: int, score: float = 1.0) -> dict:
    """Build a minimal result dict for deduplication tests."""
    return {
        "path": path,
        "start_line": start,
        "end_line": end,
        "score": score,
        "symbol": f"{path}:{start}",
    }


class TestDeduplicateByContainment:
    """Tests for deduplicate_by_containment()."""

    def test_empty_list(self):
        assert deduplicate_by_containment([]) == []

    def test_single_result_unchanged(self):
        results = [_r("a.py", 1, 10)]
        assert deduplicate_by_containment(results) == results

    def test_no_overlap_different_files(self):
        results = [_r("a.py", 1, 10), _r("b.py", 1, 10)]
        assert deduplicate_by_containment(results) == results

    def test_no_overlap_same_file(self):
        results = [_r("a.py", 1, 10), _r("a.py", 15, 25)]
        assert deduplicate_by_containment(results) == results

    def test_outer_dropped_when_inner_exists(self):
        outer = _r("a.py", 1, 50, score=0.9)
        inner = _r("a.py", 10, 30, score=0.8)
        result = deduplicate_by_containment([outer, inner])
        assert len(result) == 1
        assert result[0] is inner

    def test_inner_kept_regardless_of_order(self):
        """Order of results should not affect which is dropped."""
        outer = _r("a.py", 1, 50)
        inner = _r("a.py", 10, 30)
        result = deduplicate_by_containment([inner, outer])
        assert len(result) == 1
        assert result[0] is inner

    def test_exact_same_range_drops_one(self):
        r1 = _r("a.py", 5, 20, score=0.9)
        r2 = _r("a.py", 5, 20, score=0.8)
        result = deduplicate_by_containment([r1, r2])
        assert len(result) == 1

    def test_partial_overlap_kept(self):
        """Overlapping but non-containing ranges should both be kept."""
        r1 = _r("a.py", 1, 20)
        r2 = _r("a.py", 15, 35)
        result = deduplicate_by_containment([r1, r2])
        assert len(result) == 2

    def test_multiple_inner_results_all_kept(self):
        """Multiple methods inside one class should all be kept."""
        outer = _r("a.py", 1, 100)
        inner1 = _r("a.py", 10, 30)
        inner2 = _r("a.py", 40, 60)
        result = deduplicate_by_containment([outer, inner1, inner2])
        assert len(result) == 2
        paths_and_lines = [(r["start_line"], r["end_line"]) for r in result]
        assert (10, 30) in paths_and_lines
        assert (40, 60) in paths_and_lines

    def test_different_files_not_affected(self):
        """Containment check only applies within the same file."""
        r1 = _r("a.py", 1, 100)
        r2 = _r("b.py", 10, 30)
        result = deduplicate_by_containment([r1, r2])
        assert len(result) == 2

    def test_preserves_order(self):
        """Results that survive dedup should retain their original order."""
        r1 = _r("a.py", 5, 15, score=0.9)
        r2 = _r("b.py", 1, 50, score=0.7)
        r3 = _r("a.py", 1, 50, score=0.5)
        # r3 contains r1 → r3 is dropped
        result = deduplicate_by_containment([r1, r2, r3])
        assert len(result) == 2
        assert result[0] is r1
        assert result[1] is r2
