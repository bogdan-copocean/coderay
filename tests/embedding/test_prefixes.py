"""Tests for search prefix helpers."""

import pytest

from coderay.embedding.base import EmbedTask
from coderay.embedding.prefixes import SEARCH_PREFIXES, requires_prefix


def test_search_prefixes_document_query():
    assert "search_document" in SEARCH_PREFIXES[EmbedTask.DOCUMENT]
    assert "search_query" in SEARCH_PREFIXES[EmbedTask.QUERY]


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("nomic-ai/nomic-embed-text-v1.5-Q", True),
        ("mlx-community/nomicai-modernbert-embed-base-4bit", True),
        ("BAAI/bge-small-en-v1.5", False),
    ],
)
def test_requires_prefix(model_id, expected):
    assert requires_prefix(model_id) is expected
