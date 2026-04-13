"""Tests for embedding base utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coderay.core.config import _reset_config_for_testing, config_for_repo
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
            model=cfg.embedder.fastembed.model_name,
            dimensions=cfg.embedder.fastembed.dimensions,
            matryoshka_dimensions=cfg.embedder.fastembed.matryoshka_dimensions,
            batch_size=cfg.embedder.fastembed.batch_size,
        )

    @patch("coderay.embedding.local.LocalEmbedder")
    def test_uses_dimensions_from_config(self, mock_local_cls):
        mock_local_cls.return_value = MagicMock()
        base = config_for_repo(Path.cwd())
        _reset_config_for_testing(
            config_for_repo(
                Path.cwd(),
                {
                    "embedder": {
                        "backend": "fastembed",
                        "fastembed": {"dimensions": 123},
                    }
                },
            ),
        )
        try:
            _ = load_embedder_from_config()
            mock_local_cls.assert_called_once_with(
                model=base.embedder.fastembed.model_name,
                dimensions=123,
                matryoshka_dimensions=None,
                batch_size=base.embedder.fastembed.batch_size,
            )
        finally:
            _reset_config_for_testing(None)

    @patch(
        "coderay.embedding.backend_resolve.mlx_optional_installed",
        return_value=True,
    )
    @patch("coderay.embedding.mlx_backend.MLXEmbedder")
    def test_mlx_backend(self, mock_mlx_cls, _mock_mlx_ok):
        mock_mlx_cls.return_value = MagicMock()
        _reset_config_for_testing(
            config_for_repo(
                Path.cwd(),
                {
                    "embedder": {
                        "backend": "mlx",
                        "mlx": {
                            "model_name": "mlx-community/all-MiniLM-L6-v2-bf16",
                            "dimensions": 384,
                        },
                    }
                },
            ),
        )
        try:
            _ = load_embedder_from_config()
            mock_mlx_cls.assert_called_once_with(
                model_name="mlx-community/all-MiniLM-L6-v2-bf16",
                dimensions=384,
                matryoshka_dimensions=None,
                batch_size=256,
            )
        finally:
            _reset_config_for_testing(None)

    def test_mlx_backend_raises_when_optional_not_installed(self):
        _reset_config_for_testing(
            config_for_repo(
                Path.cwd(),
                {
                    "embedder": {
                        "backend": "mlx",
                        "mlx": {
                            "model_name": "mlx-community/all-MiniLM-L6-v2-bf16",
                            "dimensions": 384,
                        },
                    }
                },
            ),
        )
        try:
            with patch(
                "coderay.embedding.backend_resolve.mlx_optional_installed",
                return_value=False,
            ):
                with pytest.raises(RuntimeError, match="coderay\\[mlx\\]"):
                    load_embedder_from_config()
        finally:
            _reset_config_for_testing(None)
