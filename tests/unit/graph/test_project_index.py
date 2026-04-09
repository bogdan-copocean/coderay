"""Tests for module index construction and qualified import lowering."""

from __future__ import annotations

import pytest

from coderay.graph.graph_builder import build_module_index
from coderay.graph.lowering.name_bindings import ModuleResolution
from coderay.graph.project_index import PythonModuleIndex


class TestBuildModuleIndex:
    """build_module_index."""

    def test_first_path_wins(self) -> None:
        """Duplicate dotted names keep the first file path seen."""
        paths = ["pkg/a.py", "other/a.py"]
        idx = build_module_index(paths)
        assert idx["a"] == "pkg/a.py"


class TestModuleResolution:
    """ModuleResolution.resolve_qualified_import."""

    @pytest.mark.parametrize(
        "dotted,mod_name,symbol,expected",
        [
            (
                {"pkg": "root/pkg/mod.py"},
                "pkg",
                "Sym",
                "root/pkg/mod.py::Sym",
            ),
            (
                {"pkg": "root/pkg/__init__.py"},
                "pkg",
                "Sym",
                "pkg::Sym",
            ),
            (
                {"pkg.sub": "root/pkg/sub.py"},
                "pkg",
                "sub",
                "root/pkg/sub.py",
            ),
        ],
    )
    def test_qualified_import_branches(
        self,
        dotted: dict[str, str],
        mod_name: str,
        symbol: str,
        expected: str,
    ) -> None:
        """Package init vs concrete module vs package submodule file."""
        mr = ModuleResolution(PythonModuleIndex(dotted))
        assert mr.resolve_qualified_import(mod_name, symbol) == expected
