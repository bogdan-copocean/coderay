"""Tests for post-merge bare phantom CALLS rewrite."""

from __future__ import annotations

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.graph.code_graph import CodeGraph
from coderay.graph.passes.resolve_bare_phantoms import rewrite_bare_phantom_calls


class TestRewriteBarePhantomCalls:
    """rewrite_bare_phantom_calls."""

    @staticmethod
    def _fn(id_: str, fp: str) -> GraphNode:
        """Single function node."""
        return GraphNode(
            id=id_,
            kind=NodeKind.FUNCTION,
            file_path=fp,
            start_line=1,
            end_line=2,
            name=id_.split("::")[-1],
            qualified_name=id_.split("::")[-1],
        )

    def test_rewrites_when_unique_resolve(self) -> None:
        """Bare name target rewrites to full id when resolve_symbol is unique."""
        g = CodeGraph()
        g.add_node(self._fn("a.py::g", "a.py"))
        g.add_node(self._fn("a.py::caller", "a.py"))
        g.add_edge(GraphEdge(source="a.py::caller", target="g", kind=EdgeKind.CALLS))
        assert g.get_node("g") is None
        n = rewrite_bare_phantom_calls(g)
        assert n == 1
        assert not g.edge_has_kind("a.py::caller", "g", EdgeKind.CALLS)
        assert g.edge_has_kind("a.py::caller", "a.py::g", EdgeKind.CALLS)

    def test_no_rewrite_when_ambiguous(self) -> None:
        """Skip rewrite when multiple nodes share the short name."""
        g = CodeGraph()
        g.add_node(self._fn("a.py::f", "a.py"))
        g.add_node(self._fn("b.py::f", "b.py"))
        g.add_edge(GraphEdge(source="a.py::f", target="f", kind=EdgeKind.CALLS))
        assert rewrite_bare_phantom_calls(g) == 0
        assert g.edge_has_kind("a.py::f", "f", EdgeKind.CALLS)

    def test_no_rewrite_when_target_has_dot_or_qual(self) -> None:
        """Skip dotted or file-qualified phantom targets."""
        g = CodeGraph()
        g.add_node(self._fn("a.py::caller", "a.py"))
        g.add_edge(
            GraphEdge(source="a.py::caller", target="mod.sym", kind=EdgeKind.CALLS)
        )
        g.add_edge(
            GraphEdge(source="a.py::caller", target="x.py::z", kind=EdgeKind.CALLS)
        )
        assert rewrite_bare_phantom_calls(g) == 0
