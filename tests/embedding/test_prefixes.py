"""Tests for Nomic prefix helpers."""

import pytest

from coderay.embedding.base import EmbedTask
from coderay.embedding.prefixes import NOMIC_PREFIXES, is_nomic_model_id


def test_nomic_prefixes_document_query():
    """Nomic asymmetric prefixes differ for index vs search."""
    assert "search_document" in NOMIC_PREFIXES[EmbedTask.DOCUMENT]
    assert "search_query" in NOMIC_PREFIXES[EmbedTask.QUERY]


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("nomic-ai/nomic-embed-text-v1.5-Q", True),
        ("mlx-community/nomicai-modernbert-embed-base-4bit", True),
        ("BAAI/bge-small-en-v1.5", False),
    ],
)
def test_is_nomic_model_id(model_id, expected):
    assert is_nomic_model_id(model_id) is expected
