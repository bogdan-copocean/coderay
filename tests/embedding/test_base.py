"""Tests for embedding base utilities."""

from unittest.mock import MagicMock, patch

import pytest

from coderay.core.config import (
    Config,
    EmbedderConfig,
    FastembedEmbedderConfig,
    MLXEmbedderConfig,
    _reset_config_for_testing,
)
from coderay.embedding.base import Embedder, load_embedder_from_config


class TestEmbedderABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Embedder()


class TestLoadEmbedderFromConfig:
    @patch("coderay.embedding.local.LocalEmbedder")
    def test_local_provider_is_default(self, mock_local_cls, default_config):
        mock_local_cls.return_value = MagicMock()
        _ = load_embedder_from_config()
        cfg = default_config
        mock_local_cls.assert_called_once_with(
            model=cfg.embedder.fastembed.model,
            dimensions=cfg.embedder.fastembed.dimensions,
        )

    @patch("coderay.embedding.local.LocalEmbedder")
    def test_uses_dimensions_from_config(self, mock_local_cls):
        mock_local_cls.return_value = MagicMock()
        _reset_config_for_testing(
            Config(
                embedder=EmbedderConfig(
                    backend="fastembed",
                    fastembed=FastembedEmbedderConfig(dimensions=123),
                ),
            ),
        )
        try:
            _ = load_embedder_from_config()
            mock_local_cls.assert_called_once_with(
                model=Config().embedder.fastembed.model,
                dimensions=123,
            )
        finally:
            _reset_config_for_testing(None)

    @patch("coderay.embedding.mlx_backend.MLXEmbedder")
    def test_mlx_backend(self, mock_mlx_cls):
        mock_mlx_cls.return_value = MagicMock()
        _reset_config_for_testing(
            Config(
                embedder=EmbedderConfig(
                    backend="mlx",
                    mlx=MLXEmbedderConfig(
                        model="mlx-community/nomicai-modernbert-embed-base-4bit",
                        dimensions=768,
                        max_length=512,
                    ),
                ),
            ),
        )
        try:
            _ = load_embedder_from_config()
            mock_mlx_cls.assert_called_once_with(
                model_id="mlx-community/nomicai-modernbert-embed-base-4bit",
                dimensions=768,
                max_length=512,
            )
        finally:
            _reset_config_for_testing(None)
