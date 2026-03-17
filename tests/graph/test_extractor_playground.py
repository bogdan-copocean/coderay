"""Integration tests over graph_sample.py and known-gap documentation.

Handler-specific tests live in tests/graph/handlers/. This file provides:
- Full graph_sample integration smoke test
- Known-gap tests (xfail) that document missing features
"""

from pathlib import Path

import pytest

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.extractor import extract_graph_from_file

SAMPLE_PATH = Path(__file__).parent / "graph_sample.py"


@pytest.fixture
def graph():
    """Extract the full graph from graph_sample.py."""
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
    """Smoke test: full graph_sample extraction produces expected structure."""

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
    """Tests for features documented as TODOs in the extractor.

    Each test is marked xfail so CI stays green while gaps are visible.
    When a gap is fixed, the xfail will start passing and pytest will
    report it as xpass, signaling the marker should be removed.
    """

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


# ---------------------------------------------------------------------------
# Manual inspection helper
# ---------------------------------------------------------------------------


def test_print_graph(graph):
    """Print nodes and edges for manual inspection (run with -s)."""
    nodes, edges = graph
    print("\n=== NODES ===")
    for n in sorted(nodes, key=lambda x: (x.kind.value, x.qualified_name)):
        print(f"  {n.kind.value:8} {n.qualified_name}")
    print("\n=== EDGES ===")
    for kind in EdgeKind:
        kind_edges = [e for e in edges if e.kind == kind]
        if kind_edges:
            print(f"\n  {kind.value}:")
            for e in kind_edges:
                print(f"    {e.source} -> {e.target}")
