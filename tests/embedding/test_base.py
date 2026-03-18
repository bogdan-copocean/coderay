"""Tests for embedding base utilities."""

from unittest.mock import MagicMock, patch

import pytest

from coderay.core.config import Config, EmbedderConfig, _reset_config_for_testing
from coderay.embedding.base import Embedder, EmbedTask, load_embedder_from_config


class TestEmbedderABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Embedder()


class TestEmbedTask:
    def test_document_value(self):
        assert EmbedTask.DOCUMENT.value == "document"

    def test_query_value(self):
        assert EmbedTask.QUERY.value == "query"


class TestLoadEmbedderFromConfig:
    @patch("coderay.embedding.local.LocalEmbedder")
    def test_local_provider_is_default(self, mock_local_cls, default_config):
        mock_local_cls.return_value = MagicMock()
        _ = load_embedder_from_config()
        cfg = default_config
        mock_local_cls.assert_called_once_with(
            model=cfg.embedder.model,
            dimensions=cfg.embedder.dimensions,
        )

    @patch("coderay.embedding.local.LocalEmbedder")
    def test_uses_dimensions_from_config(self, mock_local_cls):
        mock_local_cls.return_value = MagicMock()
        _reset_config_for_testing(Config(embedder=EmbedderConfig(dimensions=123)))
        try:
            _ = load_embedder_from_config()
            mock_local_cls.assert_called_once_with(
                model=Config().embedder.model,
                dimensions=123,
            )
        finally:
            _reset_config_for_testing(None)
