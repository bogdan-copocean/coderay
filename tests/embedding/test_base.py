"""Tests for embedding base utilities."""

from unittest.mock import MagicMock, patch

import pytest

from coderay.embedding.base import Embedder, load_embedder_from_config


class TestEmbedderABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Embedder()


class TestLoadEmbedderFromConfig:
    @patch("coderay.embedding.local.LocalEmbedder")
    def test_local_provider_is_default(self, mock_local_cls):
        mock_local_cls.return_value = MagicMock()
        cfg = {"embedder": {"dimensions": 384}}
        _ = load_embedder_from_config(cfg)
        mock_local_cls.assert_called_once()

    def test_unknown_provider(self):
        cfg = {"embedder": {"provider": "unknown"}}
        with pytest.raises(ValueError, match="Unknown embedder"):
            load_embedder_from_config(cfg)
