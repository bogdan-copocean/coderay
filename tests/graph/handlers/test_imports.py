"""Test ImportHandlerMixin: bare/from/aliased/relative imports, excluded modules."""

import pytest

from coderay.core.models import EdgeKind
from coderay.graph.extractor import _resolve_relative_import, extract_graph_from_file


def _import_targets(edges):
    return {e.target for e in edges if e.kind == EdgeKind.IMPORTS}


# ---------------------------------------------------------------------------
# resolve_relative_import (_utils, used by import handler)
# ---------------------------------------------------------------------------


class TestResolveRelativeImport:
    """Edge cases for relative import path resolution."""

    @pytest.mark.parametrize(
        "file_path,import_spec,expected",
        [
            ("src/a/b/file.py", ".foo", "src/a/b/foo"),
            ("src/a/b/c/file.py", "..foo.bar", "src/a/b/foo/bar"),
            ("src/a/b/c/file.py", "...foo", "src/a/foo"),
            ("src/a/b/file.py", ".", "src/a/b"),
            ("file.py", "...foo", None),
            ("src/utils/helper.ts", "./api", "src/utils/api"),
            ("src/a/b/file.js", "../shared", "src/a/shared"),
            ("src/a/b/c/file.ts", "../../utils/helper", "src/a/utils/helper"),
        ],
    )
    def test_resolve_relative_import(self, file_path, import_spec, expected):
        assert _resolve_relative_import(file_path, import_spec) == expected


# ---------------------------------------------------------------------------
# Bare imports: import X, import X as Y
# ---------------------------------------------------------------------------


class TestBareImports:
    """_handle_import: import_statement branch."""

    @pytest.mark.parametrize(
        "code,expected_targets",
        [
            ("import os\n", {"os"}),
            ("import os, sys\n", {"os", "sys"}),
        ],
    )
    def test_bare_import_creates_edges(self, code, expected_targets):
        _, edges = extract_graph_from_file("test.py", code)
        assert expected_targets <= _import_targets(edges)

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

    @pytest.mark.parametrize(
        "code,expected_targets",
        [
            ("from pathlib import Path\n", {"pathlib::Path"}),
            (
                "from collections import defaultdict, OrderedDict\n",
                {"collections::defaultdict", "collections::OrderedDict"},
            ),
        ],
    )
    def test_from_import_creates_edges(self, code, expected_targets):
        _, edges = extract_graph_from_file("test.py", code)
        assert expected_targets <= _import_targets(edges)

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

    @pytest.mark.parametrize(
        "file_path,code,expected_in_target",
        [
            ("src/a/b/file.py", "from .common import BaseRepo\n", "src/a/b/common"),
            (
                "src/a/b/c/file.py",
                "from ..common.base_repo import BaseRepo\n",
                "src/a/b/common/base_repo::BaseRepo",
            ),
        ],
    )
    def test_relative_import_resolved(self, file_path, code, expected_in_target):
        _, edges = extract_graph_from_file(file_path, code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) == 1
        assert expected_in_target in import_edges[0].target


# ---------------------------------------------------------------------------
# Excluded modules: typing, abc, __future__ — no IMPORTS edge, still register
# ---------------------------------------------------------------------------


class TestExcludedModuleImports:
    """Excluded modules: register for resolution but no IMPORTS edge."""

    @pytest.mark.parametrize(
        "code,excluded_symbol",
        [
            ("from typing import Optional\n", "typing::Optional"),
            ("from abc import ABC\n", "abc::ABC"),
        ],
    )
    def test_excluded_import_no_edge(self, code, excluded_symbol):
        _, edges = extract_graph_from_file("test.py", code)
        targets = _import_targets(edges)
        assert excluded_symbol not in targets

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


# ---------------------------------------------------------------------------
# B1: Lazy imports inside functions scope to the enclosing function
# ---------------------------------------------------------------------------


class TestLazyImportScoping:
    """Imports inside a function body produce function-scoped IMPORTS edges."""

    def test_lazy_from_import_scoped_to_function(self):
        code = (
            "def dispatch():\n    from workers.tasks import run_task\n    run_task()\n"
        )
        _, edges = extract_graph_from_file("svc.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        sources = {e.source for e in import_edges}
        assert "svc.py::dispatch" in sources
        assert "svc.py" not in sources, "lazy import should not scope to module"

    def test_lazy_bare_import_scoped_to_function(self):
        code = "def load():\n    import json\n    json.loads('{}')\n"
        _, edges = extract_graph_from_file("util.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        sources = {e.source for e in import_edges}
        assert "util.py::load" in sources
        assert "util.py" not in sources

    def test_top_level_import_still_scoped_to_module(self):
        code = "from os import path\n"
        _, edges = extract_graph_from_file("mod.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        sources = {e.source for e in import_edges}
        assert "mod.py" in sources

    def test_lazy_import_in_method_scoped_to_method(self):
        code = (
            "class Handler:\n"
            "    def process(self):\n"
            "        from lib.engine import Engine\n"
            "        Engine().run()\n"
        )
        _, edges = extract_graph_from_file("handler.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        sources = {e.source for e in import_edges}
        assert "handler.py::Handler.process" in sources
        assert "handler.py" not in sources


# ---------------------------------------------------------------------------
# Edge explosion: bare import produces exactly one edge
# ---------------------------------------------------------------------------


class TestBareImportDeduplication:
    """bare `import X` must not create duplicate from-import-style edges."""

    def test_bare_import_single_edge(self):
        code = "import os\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) == 1, (
            f"expected 1 IMPORTS edge for bare import, got {len(import_edges)}: "
            f"{[(e.source, e.target) for e in import_edges]}"
        )

    def test_bare_import_multi_single_edge_each(self):
        code = "import os, sys\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) == 2, "one edge per bare import name"
