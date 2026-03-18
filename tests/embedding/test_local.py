"""Tests for local fastembed embedder (mocked model)."""

from unittest.mock import MagicMock, patch

import numpy as np

from coderay.embedding.base import EmbedTask
from coderay.embedding.local import _TASK_PREFIXES, MAX_CHARS, LocalEmbedder


class TestLocalEmbedder:
    def test_dimensions_property(self):
        e = LocalEmbedder()
        assert e.dimensions == 384

    def test_embed_empty(self):
        e = LocalEmbedder()
        assert e.embed([]) == []

    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_embed_calls_model(self, mock_load):
        e = LocalEmbedder()
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(
            [np.array([0.1] * 384), np.array([0.2] * 384)]
        )
        e._model = mock_model

        result = e.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 384
        mock_model.embed.assert_called_once()

    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_lazy_loading(self, mock_load):
        e = LocalEmbedder()
        assert e._model is None
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([np.array([0.1] * 384)])

        def _fake_load():
            e._model = mock_model

        mock_load.side_effect = _fake_load
        e.embed(["test"])
        mock_load.assert_called_once()

    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_truncates_long_text(self, mock_load):
        e = LocalEmbedder()
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([np.array([0.1] * 384)])
        e._model = mock_model

        long_text = "x" * 20000
        e.embed([long_text])
        call_args = mock_model.embed.call_args
        texts = call_args[0][0]
        assert len(texts[0]) <= MAX_CHARS + 100  # prefix overhead

    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_document_prefix_applied(self, mock_load):
        """Document task prepends 'search_document: ' for nomic models."""
        model_name = "nomic-ai/nomic-embed-text-v1.5"
        e = LocalEmbedder(model=model_name, dimensions=768)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([np.array([0.1] * 768)])
        e._model = mock_model

        e.embed(["def foo(): pass"], task=EmbedTask.DOCUMENT)
        call_args = mock_model.embed.call_args
        texts = call_args[0][0]
        expected_prefix = _TASK_PREFIXES[model_name][EmbedTask.DOCUMENT]
        assert texts[0].startswith(expected_prefix)

    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_query_prefix_applied(self, mock_load):
        """Query task prepends 'search_query: ' for nomic models."""
        model_name = "nomic-ai/nomic-embed-text-v1.5"
        e = LocalEmbedder(model=model_name, dimensions=768)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([np.array([0.1] * 768)])
        e._model = mock_model

        e.embed(["how does auth work"], task=EmbedTask.QUERY)
        call_args = mock_model.embed.call_args
        texts = call_args[0][0]
        expected_prefix = _TASK_PREFIXES[model_name][EmbedTask.QUERY]
        assert texts[0].startswith(expected_prefix)

    @patch("coderay.embedding.local.LocalEmbedder._load_model")
    def test_no_prefix_for_unknown_model(self, mock_load):
        """Models not in _TASK_PREFIXES get no prefix."""
        e = LocalEmbedder(model="some/unknown-model", dimensions=384)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([np.array([0.1] * 384)])
        e._model = mock_model

        original = "def foo(): pass"
        e.embed([original], task=EmbedTask.DOCUMENT)
        call_args = mock_model.embed.call_args
        texts = call_args[0][0]
        assert texts[0] == original
