"""Scope reconciliation: .coderay.toml drives what is indexed."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from coderay.core.config import _reset_config_for_testing
from coderay.pipeline.indexer import Indexer


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, check=True, timeout=10
    )


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "T")


def _git_commit(repo: Path, msg: str = "c") -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", msg)


def _write_config(
    primary: Path,
    *,
    extra_roots: list[dict] | None = None,
    exclude_patterns: list[str] | None = None,
) -> None:
    """Write .coderay.toml with 4-dim embedder and optional extra roots."""
    idx = (primary / ".coderay").resolve().as_posix()
    excl = exclude_patterns or []
    excl_str = ", ".join(f'"{p}"' for p in excl)

    roots = '[[index.roots]]\nrepo = "."'
    for root in extra_roots or []:
        roots += "\n\n[[index.roots]]"
        roots += f'\nrepo = "{root["repo"]}"'
        if "include" in root:
            inc = root["include"]
            if isinstance(inc, list):
                vals = ", ".join(f'"{v}"' for v in inc)
                roots += f"\ninclude = [{vals}]"
            else:
                roots += f'\ninclude = "{inc}"'
        if "alias" in root:
            roots += f'\nalias = "{root["alias"]}"'

    text = f"""\
[index]
path = "{idx}"
exclude_patterns = [{excl_str}]

{roots}

[graph]
include_external = false

[search]
metric = "cosine"
hybrid = true

[search.boosting]
penalties = []
bonuses = []

[embedder]
backend = "auto"

[embedder.fastembed]
model_name = "BAAI/bge-small-en-v1.5"
dimensions = 4
batch_size = 64

[embedder.mlx]
model_name = "mlx-community/bge-small-en-v1.5-bf16"
dimensions = 4
batch_size = 256

[watcher]
debounce = 2
"""
    (primary / ".coderay.toml").write_text(text, encoding="utf-8")


def _make_indexer(repo: Path, mock_embedder) -> Indexer:
    _reset_config_for_testing(None)
    return Indexer(repo, embedder=mock_embedder)


@pytest.fixture
def multi_repo(tmp_path: Path):
    """Create primary + external git repos with sample files."""
    primary = tmp_path / "primary"
    external = tmp_path / "external"

    _git_init(primary)
    (primary / "hello.py").write_text("def hello(): ...\n")
    _git_commit(primary, "init primary")

    _git_init(external)
    (external / "mod1").mkdir()
    (external / "mod1" / "x.py").write_text("def x(): ...\n")
    (external / "mod2").mkdir()
    (external / "mod2" / "y.py").write_text("def y(): ...\n")
    (external / "mod3").mkdir()
    (external / "mod3" / "z.py").write_text("def z(): ...\n")
    _git_commit(external, "init external")

    return primary, external


class TestScopeReconciliation:
    """Config changes are picked up by incremental builds."""

    def test_new_include_is_indexed(self, multi_repo, mock_embedder):
        """Widening include= causes new files to be indexed."""
        primary, external = multi_repo

        _write_config(
            primary,
            extra_roots=[{"repo": str(external), "include": ["mod1"]}],
        )
        idx = _make_indexer(primary, mock_embedder)
        idx.build_full()

        hashes = idx._state.file_hashes
        assert any("mod1/x.py" in k for k in hashes)
        assert not any("mod2/y.py" in k for k in hashes)

        _write_config(
            primary,
            extra_roots=[{"repo": str(external), "include": ["mod1", "mod2"]}],
        )
        idx2 = _make_indexer(primary, mock_embedder)
        result = idx2.update_incremental()

        hashes2 = idx2._state.file_hashes
        assert any("mod1/x.py" in k for k in hashes2)
        assert any("mod2/y.py" in k for k in hashes2)
        assert result.updated > 0

    def test_removed_include_is_deindexed(self, multi_repo, mock_embedder):
        """Narrowing include= causes out-of-scope files to be deindexed."""
        primary, external = multi_repo

        _write_config(
            primary,
            extra_roots=[{"repo": str(external), "include": ["mod1", "mod2", "mod3"]}],
        )
        idx = _make_indexer(primary, mock_embedder)
        idx.build_full()

        hashes = idx._state.file_hashes
        assert any("mod2/y.py" in k for k in hashes)
        assert any("mod3/z.py" in k for k in hashes)

        _write_config(
            primary,
            extra_roots=[{"repo": str(external), "include": ["mod1"]}],
        )
        idx2 = _make_indexer(primary, mock_embedder)
        result = idx2.update_incremental()

        hashes2 = idx2._state.file_hashes
        assert any("mod1/x.py" in k for k in hashes2)
        assert not any("mod2/y.py" in k for k in hashes2)
        assert not any("mod3/z.py" in k for k in hashes2)
        assert result.removed > 0

    def test_removed_checkout_is_deindexed(self, multi_repo, mock_embedder):
        """Removing an [[index.roots]] entry deindexes all its files."""
        primary, external = multi_repo

        _write_config(
            primary,
            extra_roots=[{"repo": str(external)}],
        )
        idx = _make_indexer(primary, mock_embedder)
        idx.build_full()

        ext_keys = [k for k in idx._state.file_hashes if "external" in k]
        assert len(ext_keys) >= 3

        _write_config(primary)
        idx2 = _make_indexer(primary, mock_embedder)
        result = idx2.update_incremental()

        hashes2 = idx2._state.file_hashes
        assert not any("external" in k for k in hashes2)
        assert any("primary" in k for k in hashes2)
        assert result.removed >= 3

    def test_missing_external_repo_deindexes_gracefully(
        self, multi_repo, mock_embedder
    ):
        """If external repo directory is deleted, its files are deindexed."""
        primary, external = multi_repo

        _write_config(
            primary,
            extra_roots=[{"repo": str(external)}],
        )
        idx = _make_indexer(primary, mock_embedder)
        idx.build_full()

        assert any("external" in k for k in idx._state.file_hashes)

        shutil.rmtree(external)
        idx2 = _make_indexer(primary, mock_embedder)
        result = idx2.update_incremental()

        hashes2 = idx2._state.file_hashes
        assert not any("external" in k for k in hashes2)
        assert any("primary" in k for k in hashes2)
        assert result.removed >= 3

    def test_no_change_is_noop(self, multi_repo, mock_embedder):
        """Incremental with unchanged config produces no removes or updates."""
        primary, external = multi_repo

        _write_config(
            primary,
            extra_roots=[{"repo": str(external), "include": ["mod1"]}],
        )
        idx = _make_indexer(primary, mock_embedder)
        idx.build_full()
        original_hashes = dict(idx._state.file_hashes)

        idx2 = _make_indexer(primary, mock_embedder)
        result = idx2.update_incremental()

        assert idx2._state.file_hashes == original_hashes
        assert result.removed == 0
        assert result.updated == 0
