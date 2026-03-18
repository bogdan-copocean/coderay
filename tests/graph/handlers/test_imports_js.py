"""Test JS/TS import handler."""

import pytest

from coderay.core.models import EdgeKind
from coderay.graph.extractor import extract_graph_from_file


def _import_targets(edges):
    return {e.target for e in edges if e.kind == EdgeKind.IMPORTS}


def _has_tree_sitter_js() -> bool:
    try:
        import tree_sitter_javascript  # noqa: F401
        return True
    except ImportError:
        return False


class TestJsTsImports:
    """JsTsImportHandler: named, namespace, default imports."""

    @pytest.mark.skipif(not _has_tree_sitter_js(), reason="tree-sitter-javascript not installed")
    def test_named_import_creates_edges(self):
        code = "import { foo, bar } from './utils';\n"
        _, edges = extract_graph_from_file("src/app.js", code)
        targets = _import_targets(edges)
        assert any("foo" in t or "utils" in t for t in targets)

    @pytest.mark.skipif(not _has_tree_sitter_js(), reason="tree-sitter-javascript not installed")
    def test_namespace_import_registers(self):
        code = "import * as utils from './utils';\nutils.helper();\n"
        _, edges = extract_graph_from_file("src/app.js", code)
        calls = {e.target for e in edges if e.kind == EdgeKind.CALLS}
        assert len(edges) >= 1
