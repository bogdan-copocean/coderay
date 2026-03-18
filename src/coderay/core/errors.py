"""Domain-specific error hierarchy for CodeRay.

All public errors inherit from ``CodeRayError`` so callers can catch
the base type for broad handling or individual subclasses for targeted
recovery.
"""

from __future__ import annotations


class CodeRayError(Exception):
    """Base for all CodeRay errors."""


class IndexStaleError(CodeRayError):
    """Raised when the index is in-progress or incomplete."""


class EmbeddingDimensionError(CodeRayError):
    """Raised when embedding dimensions don't match the store schema."""


class ScoreExtractionError(CodeRayError):
    """Raised when a LanceDB result row lacks the expected score field.

    This typically indicates a LanceDB version change that altered the
    output column names for vector or hybrid search results.
    """


class SearchError(CodeRayError):
    """Raised when search fails due to store or embedding issues."""
