"""Integration over graph_sample.py and known-gap xfail tests."""

from pathlib import Path

import pytest

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.extractor import extract_graph_from_file

SAMPLE_PATH = Path(__file__).parent / "graph_sample.py"


@pytest.fixture
def graph():
    """Extract full graph from graph_sample.py."""
    content = SAMPLE_PATH.read_text()
    return extract_graph_from_file(str(SAMPLE_PATH), content)


def _edge_targets(edges, kind: EdgeKind) -> set[str]:
    return {e.target for e in edges if e.kind == kind}


def _node_names(nodes, kind: NodeKind) -> set[str]:
    return {n.name for n in nodes if n.kind == kind}


# ---------------------------------------------------------------------------
# Integration smoke test
# ---------------------------------------------------------------------------


class TestGraphSampleIntegration:
    """Smoke test: graph_sample extraction produces expected structure."""

    def test_extracts_module_and_classes(self, graph):
        nodes, edges = graph
        names = _node_names(nodes, NodeKind.CLASS)
        assert "Animal" in names
        assert "Dog" in names
        assert "Service" in names

    def test_extracts_imports(self, graph):
        _, edges = graph
        targets = _edge_targets(edges, EdgeKind.IMPORTS)
        assert "os" in targets
        assert "pathlib::Path" in targets

    def test_extracts_inherits_edges(self, graph):
        _, edges = graph
        inherits = [e for e in edges if e.kind == EdgeKind.INHERITS]
        assert len(inherits) >= 1

    def test_extracts_calls_edges(self, graph):
        _, edges = graph
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        assert len(calls) >= 10


# ---------------------------------------------------------------------------
# Known gaps — xfail tests
# ---------------------------------------------------------------------------


class TestKnownGaps:
    """Xfail tests for documented extractor gaps. Remove xfail when fixed."""

    @pytest.mark.xfail(reason="TODO: lambda/comprehension scope attribution")
    def test_lambda_call_attributed_to_lambda_scope(self, graph):
        """abs() inside a lambda should be attributed to the lambda, not parent."""
        _, edges = graph
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        lambda_calls = [e for e in calls if "lambda" in e.source.lower()]
        assert len(lambda_calls) > 0

    @pytest.mark.xfail(reason="TODO: tuple unpacking in assignments")
    def test_tuple_unpacking_alias(self):
        """a, b = func() — calling a() should not produce a bare 'a' target."""
        code = "from module import get_pair\na, b = get_pair()\na()\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "a" not in targets

    @pytest.mark.xfail(reason="TODO: wildcard imports not resolved")
    def test_wildcard_import_not_resolved(self):
        """from X import * does not register names; calls remain unresolved."""
        code = "from collections import *\ndefaultdict(int)\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "collections::defaultdict" in targets
