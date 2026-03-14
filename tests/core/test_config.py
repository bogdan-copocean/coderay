"""Tests for coderay.core.config."""

import os
from pathlib import Path

from coderay.core.config import ENV_CONFIG_FILE, ENV_INDEX_DIR, Config, load_config


class TestLoadConfig:
    def test_no_config_file_uses_defaults(self, tmp_path, monkeypatch):
        # Point CODERAY_INDEX_DIR to a temp dir with no config file
        monkeypatch.setenv(ENV_INDEX_DIR, str(tmp_path))
        cfg = load_config()
        assert isinstance(cfg, Config)
        assert cfg.embedder.dimensions == 384
        assert Path(cfg.index.path) == tmp_path

    def test_with_yaml_overrides(self, tmp_path, monkeypatch):
        monkeypatch.setenv(ENV_INDEX_DIR, str(tmp_path))
        (tmp_path / "config.yaml").write_text("embedder:\n  dimensions: 64\n")
        cfg = load_config()
        assert cfg.embedder.dimensions == 64
