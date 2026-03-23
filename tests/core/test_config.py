"""Tests for coderay.core.config."""

from pathlib import Path

from coderay.core.config import (
    ENV_INDEX_DIR,
    Config,
    _reset_config_for_testing,
    get_config,
)
from coderay.embedding.backend_resolve import resolved_embedder_backend


class TestGetConfig:
    def test_no_config_file_uses_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv(ENV_INDEX_DIR, str(tmp_path))
        _reset_config_for_testing(None)
        cfg = get_config()
        assert isinstance(cfg, Config)
        ed = cfg.embedder
        want = (
            ed.mlx.dimensions
            if resolved_embedder_backend(ed.backend) == "mlx"
            else ed.fastembed.dimensions
        )
        assert cfg.embedder.effective_dimensions() == want
        assert Path(cfg.index.path) == tmp_path

    def test_with_yaml_overrides(self, tmp_path, monkeypatch):
        monkeypatch.setenv(ENV_INDEX_DIR, str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            "embedder:\n  backend: fastembed\n  fastembed:\n    dimensions: 64\n"
        )
        _reset_config_for_testing(None)
        cfg = get_config()
        assert cfg.embedder.effective_dimensions() == 64
