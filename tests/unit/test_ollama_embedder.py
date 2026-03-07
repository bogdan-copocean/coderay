"""Tests for Ollama embedder (mocked HTTP)."""

from unittest.mock import MagicMock, patch

import pytest

from indexer.embedding.ollama import OllamaEmbedder


class TestOllamaEmbedder:
    def test_dimensions_property(self):
        e = OllamaEmbedder(dimensions=768)
        assert e.dimensions == 768

    def test_embed_empty(self):
        e = OllamaEmbedder()
        assert e.embed([]) == []

    @patch("httpx.post")
    def test_embed_single(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [[0.1] * 768]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        e = OllamaEmbedder(dimensions=768)
        result = e.embed(["hello"])
        assert len(result) == 1
        assert len(result[0]) == 768
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_embed_batch(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [[0.1] * 768, [0.2] * 768]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        e = OllamaEmbedder(dimensions=768)
        result = e.embed(["hello", "world"])
        assert len(result) == 2

    @patch("httpx.post")
    def test_embed_truncates_oversized_vectors(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [[0.1] * 1024]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        e = OllamaEmbedder(dimensions=768)
        result = e.embed(["hello"])
        assert len(result[0]) == 768

    @patch.dict("os.environ", {}, clear=True)
    def test_custom_url(self):
        e = OllamaEmbedder(base_url="http://myhost:1234/")
        assert e._base_url == "http://myhost:1234"

    @patch.dict("os.environ", {"OLLAMA_HOST": "http://remote:9999"})
    def test_env_var_overrides_base_url(self):
        e = OllamaEmbedder(base_url="http://myhost:1234/")
        assert e._base_url == "http://remote:9999"

    def test_custom_model(self):
        e = OllamaEmbedder(model="mxbai-embed-large")
        assert e._model == "mxbai-embed-large"

    @patch("httpx.post")
    def test_connection_error_raises_runtime(self, mock_post):
        import httpx

        mock_post.side_effect = httpx.ConnectError("Connection refused")
        e = OllamaEmbedder(dimensions=768)
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            e.embed(["test"])

    @patch("httpx.post")
    def test_timeout_error_raises_runtime(self, mock_post):
        import httpx

        mock_post.side_effect = httpx.TimeoutException("Timed out")
        e = OllamaEmbedder(dimensions=768)
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            e.embed(["test"])
