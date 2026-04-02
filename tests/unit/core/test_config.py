"""Tests for coderay.core.config."""

from pathlib import Path

import pytest

from coderay.core.config import (
    ConfigError,
    ProjectNotInitializedError,
    _reset_config_for_testing,
    config_for_repo,
    get_config,
    render_default_toml,
    sanitize_index_root_alias_default,
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
                    'path = ".coderay"',
                    "exclude_patterns = []",
                    "",
                    "[[index.roots]]",
                    'repo = "."',
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
                    "include_external = false",
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


class TestValidateIndexRoots:
    def test_multi_root_without_dot_raises(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        with pytest.raises(ConfigError, match="exactly one"):
            config_for_repo(
                tmp_path,
                {
                    "index": {
                        "roots": [{"repo": str(a)}, {"repo": str(b)}],
                    },
                },
            )

    def test_two_dot_rows_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="exactly one"):
            config_for_repo(
                tmp_path,
                {"index": {"roots": [{"repo": "."}, {"repo": "."}]}},
            )

    @pytest.mark.parametrize(
        "roots",
        [
            [{"repo": "."}],
            [{"repo": ".", "include": "src"}],
        ],
    )
    def test_valid_project_roots(self, tmp_path: Path, roots: list) -> None:
        if any(r.get("include") for r in roots):
            (tmp_path / "src").mkdir()
        cfg = config_for_repo(tmp_path, {"index": {"roots": roots}})
        assert cfg.index.roots

    def test_valid_dot_plus_extra_repo(self, tmp_path: Path) -> None:
        other = tmp_path / "other"
        other.mkdir()
        cfg = config_for_repo(
            tmp_path,
            {
                "index": {
                    "roots": [{"repo": "."}, {"repo": str(other)}],
                },
            },
        )
        assert len(cfg.index.roots) == 2

    def test_valid_single_external_only(self, tmp_path: Path) -> None:
        ext = tmp_path / "lib"
        ext.mkdir()
        cfg = config_for_repo(
            tmp_path,
            {"index": {"roots": [{"repo": str(ext)}]}},
        )
        assert len(cfg.index.roots) == 1

    def test_duplicate_alias_raises(self, tmp_path: Path) -> None:
        o = tmp_path / "o"
        o.mkdir()
        with pytest.raises(ConfigError, match="unique"):
            config_for_repo(
                tmp_path,
                {
                    "index": {
                        "roots": [
                            {"repo": ".", "alias": "x"},
                            {"repo": str(o), "alias": "x"},
                        ],
                    },
                },
            )

    @pytest.mark.parametrize(
        "bad",
        ["a.b", "a/b", "a b", "x:y", "café", "x.y.z"],
    )
    def test_explicit_alias_invalid_chars(self, tmp_path: Path, bad: str) -> None:
        with pytest.raises(ConfigError, match="letters, digits"):
            config_for_repo(
                tmp_path,
                {"index": {"roots": [{"repo": ".", "alias": bad}]}},
            )

    def test_explicit_alias_valid_chars(self, tmp_path: Path) -> None:
        cfg = config_for_repo(
            tmp_path,
            {
                "index": {
                    "roots": [
                        {"repo": ".", "alias": "my-lib_v2"},
                    ],
                },
            },
        )
        assert cfg.index.roots[0].alias == "my-lib_v2"


class TestSanitizeIndexRootAliasDefault:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("foo.bar", "foo_bar"),
            ("my-repo", "my-repo"),
            ("a_b", "a_b"),
            ("", "root"),
            ("___", "root"),
            (".hidden", "hidden"),
        ],
    )
    def test_sanitize(self, raw: str, expected: str) -> None:
        assert sanitize_index_root_alias_default(raw) == expected
