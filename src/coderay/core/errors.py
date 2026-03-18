"""Domain-specific error hierarchy for CodeRay."""

from __future__ import annotations


class CodeRayError(Exception):
    """Base for all CodeRay errors."""


class IndexStaleError(CodeRayError):
    """Raised when the index is in-progress or incomplete."""


class EmbeddingDimensionError(CodeRayError):
    """Raised when embedding dimensions don't match the store schema."""


class ScoreExtractionError(CodeRayError):
    """Raised when a LanceDB result row lacks the expected score field."""


class SearchError(CodeRayError):
    """Raised when search fails due to store or embedding issues."""
