"""Tests for indexer.core.config."""

import pytest

from indexer.core.config import get_embedding_dimensions, load_config


class TestGetEmbeddingDimensions:
    def test_default(self):
        assert get_embedding_dimensions({}) == 384

    def test_custom(self):
        cfg = {"embedder": {"dimensions": 256}}
        assert get_embedding_dimensions(cfg) == 256

    def test_nested_missing(self):
        assert get_embedding_dimensions({"embedder": {}}) == 384


class TestLoadConfig:
    def test_no_config_file(self, tmp_path):
        cfg = load_config(tmp_path)
        assert isinstance(cfg, dict)

    def test_with_yaml(self, tmp_path):
        (tmp_path / "config.yaml").write_text("embedder:\n  dimensions: 64\n")
        cfg = load_config(tmp_path)
        assert cfg["embedder"]["dimensions"] == 64
