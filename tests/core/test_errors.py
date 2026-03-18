"""Tests for the domain error hierarchy."""

import pytest

from coderay.core.errors import (
    CodeRayError,
    EmbeddingDimensionError,
    IndexStaleError,
    ScoreExtractionError,
    SearchError,
)


class TestErrorHierarchy:
    """All domain errors inherit from CodeRayError."""

    @pytest.mark.parametrize(
        "exc_cls",
        [IndexStaleError, EmbeddingDimensionError, ScoreExtractionError, SearchError],
    )
    def test_inherits_from_base(self, exc_cls):
        assert issubclass(exc_cls, CodeRayError)

    @pytest.mark.parametrize(
        "exc_cls",
        [IndexStaleError, EmbeddingDimensionError, ScoreExtractionError, SearchError],
    )
    def test_catchable_as_base(self, exc_cls):
        with pytest.raises(CodeRayError):
            raise exc_cls("test")

    def test_score_extraction_error_message(self):
        err = ScoreExtractionError("missing _distance")
        assert "missing _distance" in str(err)
