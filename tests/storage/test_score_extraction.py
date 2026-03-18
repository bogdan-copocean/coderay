"""Test deterministic score extraction from LanceDB rows."""

import pytest

from coderay.core.errors import ScoreExtractionError
from coderay.storage.lancedb import _extract_score, _ScoreField


class TestExtractScore:
    """Test _extract_score deterministic extraction."""

    def test_relevance_score_extracted(self):
        row = {"_relevance_score": 0.85, "content": "x"}
        score = _extract_score(row, _ScoreField.RELEVANCE)
        assert score == 0.85
        assert "_relevance_score" not in row

    def test_distance_converted_to_similarity(self):
        row = {"_distance": 0.3, "content": "x"}
        score = _extract_score(row, _ScoreField.DISTANCE)
        assert score == pytest.approx(0.7)
        assert "_distance" not in row

    def test_secondary_fields_cleaned_up(self):
        row = {
            "_relevance_score": 0.9,
            "_distance": 0.1,
            "score": 5.0,
            "content": "x",
        }
        _extract_score(row, _ScoreField.RELEVANCE)
        assert "_distance" not in row
        assert "score" not in row
        assert "content" in row

    def test_missing_relevance_raises(self):
        row = {"_distance": 0.3, "content": "x"}
        with pytest.raises(ScoreExtractionError, match="_relevance_score"):
            _extract_score(row, _ScoreField.RELEVANCE)

    def test_missing_distance_raises(self):
        row = {"_relevance_score": 0.9, "content": "x"}
        with pytest.raises(ScoreExtractionError, match="_distance"):
            _extract_score(row, _ScoreField.DISTANCE)

    def test_empty_row_raises(self):
        row = {"content": "x"}
        with pytest.raises(ScoreExtractionError):
            _extract_score(row, _ScoreField.RELEVANCE)

    def test_error_message_includes_available_keys(self):
        row = {"content": "x", "path": "a.py"}
        with pytest.raises(ScoreExtractionError, match="path"):
            _extract_score(row, _ScoreField.DISTANCE)
