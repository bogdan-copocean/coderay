"""Tests for indexer.embedding."""

from unittest.mock import MagicMock, patch

import pytest

from indexer.embedding.base import Embedder, load_embedder_from_config
from indexer.embedding.openai import OpenAIEmbedder


class TestEmbedderABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Embedder()


class TestOpenAIEmbedder:
    @patch("openai.OpenAI")
    def test_embed_returns_vectors(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_resp
        emb = OpenAIEmbedder(model="test", dimensions=3, api_key="fake")
        result = emb.embed(["hello"])
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

    @patch("openai.OpenAI")
    def test_embed_batching(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.1] * 3) for _ in range(3)]
        mock_client.embeddings.create.return_value = mock_resp
        emb = OpenAIEmbedder(model="test", dimensions=3, api_key="fake")
        result = emb.embed(["a", "b", "c"])
        assert len(result) == 3

    def test_dimensions_property(self):
        with patch("openai.OpenAI"):
            emb = OpenAIEmbedder(model="test", dimensions=128, api_key="fake")
            assert emb.dimensions == 128

    @patch("openai.OpenAI")
    def test_truncates_long_text(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.1] * 3)]
        mock_client.embeddings.create.return_value = mock_resp

        emb = OpenAIEmbedder(model="test", dimensions=3, api_key="fake")
        long_text = "x" * 20000
        emb.embed([long_text])
        call_args = mock_client.embeddings.create.call_args
        sent_text = call_args.kwargs.get("input", call_args[1].get("input", []))[0]
        assert len(sent_text) <= 8000


class TestLoadEmbedderFromConfig:
    @patch("openai.OpenAI")
    def test_openai_provider(self, _):
        cfg = {
            "embedder": {
                "provider": "openai",
                "model": "test",
                "dimensions": 10,
                "api_key": "fake",
            }
        }
        emb = load_embedder_from_config(cfg)
        assert isinstance(emb, OpenAIEmbedder)

    @patch("indexer.embedding.local.LocalEmbedder")
    def test_local_provider_is_default(self, mock_local_cls):
        mock_local_cls.return_value = MagicMock()
        cfg = {"embedder": {"dimensions": 384}}
        emb = load_embedder_from_config(cfg)
        mock_local_cls.assert_called_once()

    def test_unknown_provider(self):
        cfg = {"embedder": {"provider": "unknown"}}
        with pytest.raises(ValueError, match="Unknown embedder"):
            load_embedder_from_config(cfg)
