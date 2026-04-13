"""Tests for local fastembed embedder (mocked model)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from coderay.embedding.base import EmbedTask
from coderay.embedding.local import LocalEmbedder
from coderay.embedding.prefixes import SEARCH_PREFIXES


def _embed_side_effect(dim: int):
    """Return side_effect for TextEmbedding.embed yielding one vector per document."""

    def _side_effect(documents, batch_size=256, parallel=None, **kwargs):
        if isinstance(documents, str):
            texts = [documents]
        else:
            texts = list(documents)
        return iter([np.array([0.1] * dim) for _ in texts])

    return _side_effect


class TestLocalEmbedder:
    def test_embed_empty(self):
        e = LocalEmbedder(
            model="sentence-transformers/all-MiniLM-L6-v2", dimensions=384
        )
        assert e.embed([]) == []

    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_embed_calls_model(self, mock_load):
        e = LocalEmbedder(
            model="sentence-transformers/all-MiniLM-L6-v2", dimensions=768
        )
        mock_model = MagicMock()
        mock_model.embed.side_effect = _embed_side_effect(768)
        e._model = mock_model

        result = e.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 768
        mock_model.embed.assert_called_once()

    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_lazy_loading(self, mock_load):
        e = LocalEmbedder(
            model="sentence-transformers/all-MiniLM-L6-v2", dimensions=384
        )
        assert e._model is None
        mock_model = MagicMock()
        mock_model.embed.side_effect = _embed_side_effect(768)

        def _fake_load():
            e._model = mock_model

        mock_load.side_effect = _fake_load
        e.embed(["test"])
        mock_load.assert_called_once()

    @pytest.mark.parametrize(
        "model,task,input_text,expected_prefix",
        [
            (
                "nomic-ai/nomic-embed-text-v1.5",
                EmbedTask.DOCUMENT,
                "def foo(): pass",
                SEARCH_PREFIXES[EmbedTask.DOCUMENT],
            ),
            (
                "nomic-ai/nomic-embed-text-v1.5",
                EmbedTask.QUERY,
                "how does auth work",
                SEARCH_PREFIXES[EmbedTask.QUERY],
            ),
            ("some/unknown-model", EmbedTask.DOCUMENT, "def foo(): pass", None),
        ],
    )
    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_task_prefix_behavior(
        self, mock_load, model, task, input_text, expected_prefix
    ):
        dims = 768 if "nomic" in model else 384
        e = LocalEmbedder(model=model, dimensions=dims)
        mock_model = MagicMock()
        mock_model.embed.side_effect = _embed_side_effect(dims)
        e._model = mock_model

        e.embed([input_text], task=task)
        texts = mock_model.embed.call_args[0][0]
        if expected_prefix:
            assert texts[0].startswith(expected_prefix)
        else:
            assert texts[0] == input_text
