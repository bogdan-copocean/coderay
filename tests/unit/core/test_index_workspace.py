"""Tests for coderay.core.index_workspace."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pathspec
import pytest

from coderay.core.config import config_for_repo
from coderay.core.index_workspace import IndexWorkspace, resolve_index_workspace


class TestResolveIndexWorkspace:
    def test_default_single_root_matches_config_repo(self, tmp_path: Path) -> None:
        cfg = config_for_repo(tmp_path, {})
        ws = resolve_index_workspace(tmp_path, cfg)
        assert len(ws.roots) == 1
        assert ws.roots[0].alias == tmp_path.name
        assert ws.roots[0].repo_root == tmp_path.resolve()
        assert ws.roots[0].scopes is None
        assert ws.roots[0].is_primary_checkout is True
        assert ws.primary_alias == ws.roots[0].alias

    def test_include_on_project_row(self, tmp_path: Path) -> None:
        (tmp_path / "packages" / "app").mkdir(parents=True)
        cfg = config_for_repo(
            tmp_path,
            {
                "index": {
                    "roots": [{"repo": ".", "include": "packages/app"}],
                },
            },
        )
        ws = resolve_index_workspace(tmp_path, cfg)
        assert ws.roots[0].scopes == ((tmp_path / "packages" / "app").resolve(),)

    def test_include_list_union(self, tmp_path: Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        cfg = config_for_repo(
            tmp_path,
            {
                "index": {
                    "roots": [
                        {"repo": ".", "include": ["a", "b"]},
                    ],
                },
            },
        )
        ws = resolve_index_workspace(tmp_path, cfg)
        ra, rb = (tmp_path / "a").resolve(), (tmp_path / "b").resolve()
        assert set(ws.roots[0].scopes or ()) == {ra, rb}
        assert ws.roots[0].contains_path(tmp_path / "a" / "x.py")
        assert not ws.roots[0].contains_path(tmp_path / "c" / "x.py")

    def test_explicit_roots_second_repo(self, tmp_path: Path) -> None:
        other = tmp_path / "other"
        other.mkdir()
        cfg = config_for_repo(
            tmp_path,
            {
                "index": {
                    "roots": [
                        {"repo": ".", "include": None},
                        {"repo": str(other), "include": None},
                    ],
                },
            },
        )
        ws = resolve_index_workspace(tmp_path, cfg)
        assert len(ws.roots) == 2
        assert ws.roots[0].alias == tmp_path.name
        assert ws.roots[1].alias == "other"
        assert ws.roots[1].repo_root == other.resolve()
        assert ws.primary_alias == ws.roots[0].alias

    def test_logical_key_roundtrip(self, tmp_path: Path) -> None:
        cfg = config_for_repo(tmp_path, {})
        ws = resolve_index_workspace(tmp_path, cfg)
        f = tmp_path / "a.py"
        f.write_text("x=1\n")
        alias = ws.roots[0].alias
        k = ws.logical_key(ws.roots[0], f)
        assert k == f"{alias}/a.py"
        assert ws.resolve_logical(k) == f.resolve()

    @pytest.mark.parametrize(
        "explicit,expect_second",
        [
            ("mylib", "mylib"),
            (None, "dup-2"),
        ],
    )
    def test_alias_collision_basename(
        self, tmp_path: Path, explicit: str | None, expect_second: str
    ) -> None:
        """Additional checkouts with same basename get -2/-3 unless alias is set."""
        one = tmp_path / "r1" / "dup"
        two = tmp_path / "r2" / "dup"
        one.mkdir(parents=True)
        two.mkdir(parents=True)
        roots = [
            {"repo": "."},
            {"repo": str(one)},
            {
                "repo": str(two),
                **({} if explicit is None else {"alias": explicit}),
            },
        ]
        cfg = config_for_repo(tmp_path, {"index": {"roots": roots}})
        ws = resolve_index_workspace(tmp_path, cfg)
        aliases = {r.alias for r in ws.roots}
        assert "dup" in aliases
        assert expect_second in aliases


def test_index_workspace_frozen() -> None:
    ws = IndexWorkspace(
        config_repo_root=Path("/tmp"),
        roots=(),
        index_dir=Path("/tmp/.coderay"),
        index_exclude=pathspec.PathSpec.from_lines("gitignore", []),
    )
    with pytest.raises(FrozenInstanceError):
        ws.config_repo_root = Path("/x")  # type: ignore[misc]


def test_resolved_checkout_requires_repo_relative_include(tmp_path: Path) -> None:
    """include outside repo raises from resolve (validator)."""
    cfg = config_for_repo(
        tmp_path,
        {"index": {"roots": [{"repo": ".", "include": "../outside"}]}},
    )
    with pytest.raises(ValueError, match="escapes repo"):
        resolve_index_workspace(tmp_path, cfg)
