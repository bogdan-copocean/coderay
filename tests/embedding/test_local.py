"""Tests for local fastembed embedder (mocked model)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from coderay.embedding.base import EmbedTask
from coderay.embedding.local import _TASK_PREFIXES, MAX_CHARS, LocalEmbedder


class TestLocalEmbedder:
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

    @pytest.mark.parametrize(
        "model,task,input_text,expected_prefix",
        [
            (
                "nomic-ai/nomic-embed-text-v1.5",
                EmbedTask.DOCUMENT,
                "def foo(): pass",
                _TASK_PREFIXES["nomic-ai/nomic-embed-text-v1.5"][EmbedTask.DOCUMENT],
            ),
            (
                "nomic-ai/nomic-embed-text-v1.5",
                EmbedTask.QUERY,
                "how does auth work",
                _TASK_PREFIXES["nomic-ai/nomic-embed-text-v1.5"][EmbedTask.QUERY],
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
        mock_model.embed.return_value = iter([np.array([0.1] * dims)])
        e._model = mock_model

        e.embed([input_text], task=task)
        texts = mock_model.embed.call_args[0][0]
        if expected_prefix:
            assert texts[0].startswith(expected_prefix)
        else:
            assert texts[0] == input_text
