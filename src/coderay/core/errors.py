"""CodeRay error hierarchy."""

from __future__ import annotations


class CodeRayError(Exception):
    """Base for all CodeRay errors."""


class IndexStaleError(CodeRayError):
    """Raised when index is in-progress or incomplete."""


class EmbeddingDimensionError(CodeRayError):
    """Raised when embedding dimensions don't match store."""


class ScoreExtractionError(CodeRayError):
    """Raised when LanceDB row lacks score field."""


class SearchError(CodeRayError):
    """Raised when search fails (store or embedding)."""
