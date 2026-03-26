"""Tests for coderay.core.config."""

from pathlib import Path

from coderay.core.config import (
    Config,
    ProjectNotInitializedError,
    _reset_config_for_testing,
    get_config,
    render_default_toml,
)
from coderay.embedding.backend_resolve import resolved_embedder_backend


class TestGetConfig:
    def test_no_config_file_uses_defaults(self, tmp_path, monkeypatch):
        _reset_config_for_testing(None)
        try:
            get_config(tmp_path)
        except ProjectNotInitializedError:
            return
        raise AssertionError("Expected ProjectNotInitializedError")

    def test_with_default_toml(self, tmp_path: Path):
        (tmp_path / ".coderay.toml").write_text(render_default_toml(tmp_path))
        _reset_config_for_testing(None)
        cfg = get_config(tmp_path)
        ed = cfg.embedder
        want = (
            ed.mlx.dimensions
            if resolved_embedder_backend(ed.backend) == "mlx"
            else ed.fastembed.dimensions
        )
        assert cfg.embedder.effective_dimensions() == want
        assert Path(cfg.index.path) == (tmp_path / ".coderay").resolve()

    def test_with_toml_overrides(self, tmp_path: Path):
        (tmp_path / ".coderay.toml").write_text(
            "\n".join(
                [
                    "[index]",
                    'dir = ".coderay"',
                    "paths = []",
                    "exclude_patterns = []",
                    "",
                    "[search]",
                    'metric = "cosine"',
                    "hybrid = true",
                    "",
                    "[search.boosting]",
                    "penalties = []",
                    "bonuses = []",
                    "",
                    "[graph]",
                    "exclude_modules = []",
                    "include_modules = []",
                    "",
                    "[watcher]",
                    "debounce = 2",
                    "",
                    "[embedder]",
                    'backend = "fastembed"',
                    "",
                    "[embedder.fastembed]",
                    'model_name = "BAAI/bge-small-en-v1.5"',
                    "dimensions = 64",
                    "batch_size = 64",
                    "",
                    "[embedder.mlx]",
                    'model_name = "mlx-community/bge-small-en-v1.5-bf16"',
                    "dimensions = 384",
                    "batch_size = 256",
                    "",
                ]
            )
        )
        _reset_config_for_testing(None)
        cfg = get_config(tmp_path)
        assert cfg.embedder.effective_dimensions() == 64
