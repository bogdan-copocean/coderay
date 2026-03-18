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
    @pytest.mark.parametrize(
        "exc_cls",
        [IndexStaleError, EmbeddingDimensionError, ScoreExtractionError, SearchError],
    )
    def test_inherits_and_catchable_as_base(self, exc_cls):
        assert issubclass(exc_cls, CodeRayError)
        with pytest.raises(CodeRayError):
            raise exc_cls("test")

    def test_score_extraction_error_message(self):
        err = ScoreExtractionError("missing _distance")
        assert "missing _distance" in str(err)
