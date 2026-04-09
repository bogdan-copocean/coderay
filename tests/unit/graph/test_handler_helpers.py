"""Tests for pure graph handler helpers."""

from __future__ import annotations

import pytest

from coderay.graph.handlers.helpers import resolve_base_class_name


class _Bindings:
    """Minimal NameBindings stub."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._m = mapping

    def resolve(self, name: str) -> str | None:
        return self._m.get(name)


class TestResolveBaseClassName:
    """resolve_base_class_name."""

    @pytest.mark.parametrize(
        "raw,mapping,expected",
        [
            ("Base", {"Base": "m.py::Base"}, "m.py::Base"),
            ("Base", {}, "Base"),
            ("alias.Sub", {"alias": "pkg.py::pkg"}, "pkg.py::pkg.Sub"),
            ("alias.Sub", {}, "alias.Sub"),
        ],
    )
    def test_matrix(self, raw: str, mapping: dict[str, str], expected: str) -> None:
        """Resolve simple or dotted base names through bindings."""
        assert resolve_base_class_name(raw, _Bindings(mapping)) == expected
