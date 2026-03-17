"""Tests for ImportHandlerMixin: IMPORTS edges and FileContext registration.

Covers: bare imports, from-imports, aliased imports, relative imports,
excluded modules.
"""

from coderay.core.models import EdgeKind
from coderay.graph.extractor import _resolve_relative_import, extract_graph_from_file


def _import_targets(edges):
    return {e.target for e in edges if e.kind == EdgeKind.IMPORTS}


# ---------------------------------------------------------------------------
# resolve_relative_import (_utils, used by import handler)
# ---------------------------------------------------------------------------


class TestResolveRelativeImport:
    """Edge cases for relative import path resolution."""

    def test_single_dot_current_package(self):
        assert _resolve_relative_import("src/a/b/file.py", ".foo") == "src/a/b/foo"

    def test_double_dot_parent_package(self):
        assert (
            _resolve_relative_import("src/a/b/c/file.py", "..foo.bar")
            == "src/a/b/foo/bar"
        )

    def test_triple_dot_two_levels_up(self):
        assert (
            _resolve_relative_import("src/a/b/c/file.py", "...foo") == "src/a/foo"
        )

    def test_dot_only_current_package(self):
        assert _resolve_relative_import("src/a/b/file.py", ".") == "src/a/b"

    def test_too_many_dots_returns_none(self):
        assert _resolve_relative_import("file.py", "...foo") is None


# ---------------------------------------------------------------------------
# Bare imports: import X, import X as Y
# ---------------------------------------------------------------------------


class TestBareImports:
    """_handle_import: import_statement branch."""

    def test_single_bare_import_creates_edge(self):
        _, edges = extract_graph_from_file("test.py", "import os\n")
        assert "os" in _import_targets(edges)

    def test_multiple_bare_imports_comma_separated(self):
        _, edges = extract_graph_from_file("test.py", "import os, sys\n")
        targets = _import_targets(edges)
        assert "os" in targets
        assert "sys" in targets

    def test_aliased_bare_import_registers_alias(self):
        """import math as m — edge target is 'math', m() resolves to math."""
        _, edges = extract_graph_from_file("test.py", "import math as m\nm.sqrt(4)\n")
        targets = _import_targets(edges)
        assert "math" in targets
        assert "m" not in targets
        calls = {e.target for e in edges if e.kind == EdgeKind.CALLS}
        assert "math.sqrt" in calls


# ---------------------------------------------------------------------------
# From imports: from X import Y, from X import Y as Z
# ---------------------------------------------------------------------------


class TestFromImports:
    """_handle_import: import_from_statement branch."""

    def test_from_import_single_symbol(self):
        _, edges = extract_graph_from_file("test.py", "from pathlib import Path\n")
        assert "pathlib::Path" in _import_targets(edges)

    def test_from_import_multiple_symbols(self):
        _, edges = extract_graph_from_file(
            "test.py", "from collections import defaultdict, OrderedDict\n"
        )
        targets = _import_targets(edges)
        assert "collections::defaultdict" in targets
        assert "collections::OrderedDict" in targets

    def test_aliased_from_import_uses_original_in_edge(self):
        """from collections import defaultdict as dd — target has original name."""
        _, edges = extract_graph_from_file(
            "test.py", "from collections import defaultdict as dd\ndd(int)\n"
        )
        targets = _import_targets(edges)
        assert "collections::defaultdict" in targets
        assert "dd" not in targets
        calls = {e.target for e in edges if e.kind == EdgeKind.CALLS}
        assert "collections::defaultdict" in calls


# ---------------------------------------------------------------------------
# Relative imports
# ---------------------------------------------------------------------------


class TestRelativeImports:
    """_resolve_import_text: relative paths resolved via module index."""

    def test_relative_import_single_dot_resolved(self):
        code = "from .common import BaseRepo\n"
        _, edges = extract_graph_from_file("src/a/b/file.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) == 1
        assert "src/a/b/common" in import_edges[0].target

    def test_relative_import_double_dot_resolved(self):
        code = "from ..common.base_repo import BaseRepo\n"
        _, edges = extract_graph_from_file("src/a/b/c/file.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) == 1
        assert "src/a/b/common/base_repo::BaseRepo" in import_edges[0].target


# ---------------------------------------------------------------------------
# Excluded modules: typing, abc, __future__ — no IMPORTS edge, still register
# ---------------------------------------------------------------------------


class TestExcludedModuleImports:
    """Excluded modules: register for resolution but no IMPORTS edge."""

    def test_typing_import_no_edge(self):
        _, edges = extract_graph_from_file("test.py", "from typing import Optional\n")
        targets = _import_targets(edges)
        assert "typing::Optional" not in targets

    def test_abc_import_no_edge(self):
        _, edges = extract_graph_from_file("test.py", "from abc import ABC\n")
        targets = _import_targets(edges)
        assert "abc::ABC" not in targets

    def test_excluded_import_still_resolves_calls(self):
        """cast() from typing — no IMPORTS edge but call resolution works."""
        code = "from typing import cast\ncast(str, x)\n"
        _, edges = extract_graph_from_file("test.py", code)
        assert "typing::cast" not in _import_targets(edges)
        # Call is filtered (excluded module) but resolution path exists
        call_targets = {e.target for e in edges if e.kind == EdgeKind.CALLS}
        assert "typing::cast" not in call_targets  # filtered by _is_excluded

    def test_non_excluded_import_creates_edge(self):
        _, edges = extract_graph_from_file("test.py", "from flask import Flask\n")
        assert "flask::Flask" in _import_targets(edges)


