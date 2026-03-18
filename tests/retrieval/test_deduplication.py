"""Tests for deduplication and relevance tier assignment in Retrieval."""

from coderay.retrieval.models import SearchResult
from coderay.retrieval.search import Retrieval


def _r(path: str, start: int, end: int, score: float = 1.0) -> SearchResult:
    """Build a minimal SearchResult for tests."""
    return SearchResult(
        path=path,
        start_line=start,
        end_line=end,
        symbol=f"{path}:{start}",
        content="",
        score=score,
    )


class TestDeduplicateByContainment:
    """Tests for Retrieval._deduplicate_by_containment()."""

    def test_empty_list(self):
        assert Retrieval._deduplicate_by_containment([]) == []

    def test_single_result_unchanged(self):
        results = [_r("a.py", 1, 10)]
        assert Retrieval._deduplicate_by_containment(results) == results

    def test_no_overlap_different_files(self):
        results = [_r("a.py", 1, 10), _r("b.py", 1, 10)]
        assert Retrieval._deduplicate_by_containment(results) == results

    def test_no_overlap_same_file(self):
        results = [_r("a.py", 1, 10), _r("a.py", 15, 25)]
        assert Retrieval._deduplicate_by_containment(results) == results

    def test_outer_dropped_when_inner_exists(self):
        outer = _r("a.py", 1, 50, score=0.9)
        inner = _r("a.py", 10, 30, score=0.8)
        result = Retrieval._deduplicate_by_containment([outer, inner])
        assert len(result) == 1
        assert result[0] is inner

    def test_inner_kept_regardless_of_order(self):
        """Order of results should not affect which is dropped."""
        outer = _r("a.py", 1, 50)
        inner = _r("a.py", 10, 30)
        result = Retrieval._deduplicate_by_containment([inner, outer])
        assert len(result) == 1
        assert result[0] is inner

    def test_exact_same_range_drops_one(self):
        r1 = _r("a.py", 5, 20, score=0.9)
        r2 = _r("a.py", 5, 20, score=0.8)
        result = Retrieval._deduplicate_by_containment([r1, r2])
        assert len(result) == 1

    def test_partial_overlap_kept(self):
        """Overlapping but non-containing ranges should both be kept."""
        r1 = _r("a.py", 1, 20)
        r2 = _r("a.py", 15, 35)
        result = Retrieval._deduplicate_by_containment([r1, r2])
        assert len(result) == 2

    def test_multiple_inner_results_all_kept(self):
        """Multiple methods inside one class should all be kept."""
        outer = _r("a.py", 1, 100)
        inner1 = _r("a.py", 10, 30)
        inner2 = _r("a.py", 40, 60)
        result = Retrieval._deduplicate_by_containment([outer, inner1, inner2])
        assert len(result) == 2
        lines = [(r.start_line, r.end_line) for r in result]
        assert (10, 30) in lines
        assert (40, 60) in lines

    def test_different_files_not_affected(self):
        """Containment check only applies within the same file."""
        r1 = _r("a.py", 1, 100)
        r2 = _r("b.py", 10, 30)
        result = Retrieval._deduplicate_by_containment([r1, r2])
        assert len(result) == 2

    def test_preserves_order(self):
        """Results that survive dedup should retain their original order."""
        r1 = _r("a.py", 5, 15, score=0.9)
        r2 = _r("b.py", 1, 50, score=0.7)
        r3 = _r("a.py", 1, 50, score=0.5)
        result = Retrieval._deduplicate_by_containment([r1, r2, r3])
        assert len(result) == 2
        assert result[0] is r1
        assert result[1] is r2


class TestAssignRelevance:
    """Tests for Retrieval._assign_relevance() tiered scoring."""

    def test_empty_list(self):
        assert Retrieval._assign_relevance([]) == []

    def test_single_result_stays_high(self):
        results = [_r("a.py", 1, 10, score=0.5)]
        marked = Retrieval._assign_relevance(results)
        assert marked[0].relevance == "high"

    def test_gradual_decay_all_high(self):
        """Scores decaying gradually should remain high."""
        results = [
            _r("a.py", 1, 10, score=0.9),
            _r("a.py", 11, 20, score=0.7),
            _r("a.py", 21, 30, score=0.55),
        ]
        marked = Retrieval._assign_relevance(results)
        assert all(r.relevance == "high" for r in marked)

    def test_single_sharp_drop_marks_medium(self):
        """A >50% drop between consecutive results marks the rest as medium."""
        results = [
            _r("a.py", 1, 10, score=0.9),
            _r("a.py", 11, 20, score=0.85),
            _r("a.py", 21, 30, score=0.3),
            _r("a.py", 31, 40, score=0.2),
        ]
        marked = Retrieval._assign_relevance(results)
        assert marked[0].relevance == "high"
        assert marked[1].relevance == "high"
        assert marked[2].relevance == "medium"
        assert marked[3].relevance == "medium"

    def test_two_drops_give_high_medium_low(self):
        """Two significant drops produce all three tiers."""
        results = [
            _r("a.py", 1, 10, score=0.9),
            _r("a.py", 11, 20, score=0.85),
            _r("a.py", 21, 30, score=0.3),
            _r("a.py", 31, 40, score=0.25),
            _r("a.py", 41, 50, score=0.05),
        ]
        marked = Retrieval._assign_relevance(results)
        assert marked[0].relevance == "high"
        assert marked[1].relevance == "high"
        assert marked[2].relevance == "medium"
        assert marked[3].relevance == "medium"
        assert marked[4].relevance == "low"

    def test_rrf_scores_sharp_drop(self):
        """Works with small RRF scores that have a proportional gap."""
        results = [
            _r("a.py", 1, 10, score=0.032),
            _r("a.py", 11, 20, score=0.028),
            _r("a.py", 21, 30, score=0.027),
            _r("a.py", 31, 40, score=0.005),
        ]
        marked = Retrieval._assign_relevance(results)
        assert marked[0].relevance == "high"
        assert marked[1].relevance == "high"
        assert marked[2].relevance == "high"
        assert marked[3].relevance == "medium"

    def test_zero_score_predecessor_skipped(self):
        """A zero-score predecessor should not cause division errors."""
        results = [
            _r("a.py", 1, 10, score=0.5),
            _r("a.py", 11, 20, score=0.0),
            _r("a.py", 21, 30, score=0.0),
        ]
        marked = Retrieval._assign_relevance(results)
        assert len(marked) == 3

    def test_all_equal_scores_remain_high(self):
        """When all scores are equal, everything is high."""
        results = [
            _r("a.py", 1, 10, score=0.5),
            _r("a.py", 11, 20, score=0.5),
            _r("a.py", 21, 30, score=0.5),
        ]
        marked = Retrieval._assign_relevance(results)
        assert all(r.relevance == "high" for r in marked)
