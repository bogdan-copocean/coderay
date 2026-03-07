"""Tests for local fastembed embedder (mocked model)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from indexer.embedding.local import LocalEmbedder


class TestLocalEmbedder:
    def test_dimensions_property(self):
        e = LocalEmbedder(dimensions=384)
        assert e.dimensions == 384

    def test_embed_empty(self):
        e = LocalEmbedder()
        assert e.embed([]) == []

    @patch("indexer.embedding.local.LocalEmbedder._load_model")
    def test_embed_calls_model(self, mock_load):
        e = LocalEmbedder(dimensions=384)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(
            [np.array([0.1] * 384), np.array([0.2] * 384)]
        )
        e._model = mock_model

        result = e.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 384
        mock_model.embed.assert_called_once()

    @patch("indexer.embedding.local.LocalEmbedder._load_model")
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

    @patch("indexer.embedding.local.LocalEmbedder._load_model")
    def test_truncates_long_text(self, mock_load):
        e = LocalEmbedder(dimensions=384)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([np.array([0.1] * 384)])
        e._model = mock_model

        long_text = "x" * 20000
        e.embed([long_text])
        call_args = mock_model.embed.call_args
        texts = call_args[0][0]
        assert len(texts[0]) <= 1500
