"""Invariant: fact stream emits expected node/edge counts."""

from __future__ import annotations

import pytest

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.emit import emit_graph
from coderay.graph.facts import CallsEdge, ModuleInfo, SymbolDefinition


@pytest.mark.parametrize(
    "facts,expected_nodes,expected_edges",
    [
        (
            [
                ModuleInfo("pkg/mod.py", 10),
                SymbolDefinition(
                    "pkg/mod.py",
                    (),
                    "f",
                    NodeKind.FUNCTION,
                    2,
                    3,
                    "pkg/mod.py",
                ),
                CallsEdge("pkg/mod.py::f", "builtins.len"),
            ],
            2,
            2,
        ),
    ],
)
def test_emit_graph_structure(facts, expected_nodes, expected_edges):
    nodes, edges = emit_graph(facts)
    assert len(nodes) == expected_nodes
    assert len(edges) == expected_edges
    kinds = {e.kind for e in edges}
    assert EdgeKind.DEFINES in kinds
    assert EdgeKind.CALLS in kinds
