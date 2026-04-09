"""Tests for impact-radius traversal on synthetic graphs."""

from __future__ import annotations

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.graph.code_graph import CodeGraph
from coderay.graph.impact import ImpactAnalyzer


class TestImpactAnalyzer:
    """ImpactAnalyzer.get_impact_radius on hand-built graphs."""

    @staticmethod
    def _mod(fp: str) -> GraphNode:
        """Module node."""
        return GraphNode(
            id=fp,
            kind=NodeKind.MODULE,
            file_path=fp,
            start_line=1,
            end_line=1,
            name=fp,
            qualified_name=fp,
        )

    @staticmethod
    def _fn(nid: str, fp: str, qn: str) -> GraphNode:
        """Function node."""
        short = qn.split(".")[-1]
        return GraphNode(
            id=nid,
            kind=NodeKind.FUNCTION,
            file_path=fp,
            start_line=1,
            end_line=2,
            name=short,
            qualified_name=qn,
        )

    @staticmethod
    def _cls(nid: str, fp: str, name: str) -> GraphNode:
        """Class node."""
        return GraphNode(
            id=nid,
            kind=NodeKind.CLASS,
            file_path=fp,
            start_line=1,
            end_line=3,
            name=name,
            qualified_name=name,
        )

    def test_includes_direct_caller(self) -> None:
        """Reverse BFS from callee reaches immediate caller."""
        g = CodeGraph()
        for n in (
            self._mod("c.py"),
            self._fn("c.py::caller", "c.py", "caller"),
            self._fn("c.py::callee", "c.py", "callee"),
        ):
            g.add_node(n)
        g.add_edge(
            GraphEdge(source="c.py::caller", target="c.py::callee", kind=EdgeKind.CALLS)
        )
        r = ImpactAnalyzer(g).get_impact_radius("c.py::callee", depth=2)
        ids = {n.id for n in r.nodes}
        assert "c.py::caller" in ids

    def test_depth_limits_hops(self) -> None:
        """Deeper chains need higher depth to reach root caller."""
        g = CodeGraph()
        for n in (
            self._mod("d.py"),
            self._fn("d.py::a", "d.py", "a"),
            self._fn("d.py::b", "d.py", "b"),
            self._fn("d.py::c", "d.py", "c"),
        ):
            g.add_node(n)
        g.add_edge(GraphEdge(source="d.py::a", target="d.py::b", kind=EdgeKind.CALLS))
        g.add_edge(GraphEdge(source="d.py::b", target="d.py::c", kind=EdgeKind.CALLS))
        shallow = ImpactAnalyzer(g).get_impact_radius("d.py::c", depth=1)
        assert {n.id for n in shallow.nodes} == {"d.py::b"}
        deep = ImpactAnalyzer(g).get_impact_radius("d.py::c", depth=2)
        assert "d.py::a" in {n.id for n in deep.nodes}

    def test_ambiguous_hint(self) -> None:
        """Unresolved duplicate short names surface ambiguity hint."""
        g = CodeGraph()
        g.add_node(self._mod("a.py"))
        g.add_node(self._fn("a.py::x", "a.py", "x"))
        g.add_node(self._mod("b.py"))
        g.add_node(self._fn("b.py::x", "b.py", "x"))
        g.add_edge(GraphEdge(source="a.py", target="b.py", kind=EdgeKind.IMPORTS))
        r = ImpactAnalyzer(g).get_impact_radius("x")
        assert r.resolved_node is None
        assert r.hint is not None
        assert "ambiguous" in r.hint.lower()

    def test_inheritance_seed_includes_base_method_callers(self) -> None:
        """Changing child method also seeds parent method for upstream callers."""
        g = CodeGraph()
        for n in (
            self._mod("m.py"),
            self._mod("u.py"),
            self._cls("m.py::Base", "m.py", "Base"),
            self._cls("m.py::Child", "m.py", "Child"),
            self._fn("m.py::Base.m", "m.py", "Base.m"),
            self._fn("m.py::Child.m", "m.py", "Child.m"),
            self._fn("u.py::use", "u.py", "use"),
        ):
            g.add_node(n)
        g.add_edge(
            GraphEdge(source="m.py::Child", target="m.py::Base", kind=EdgeKind.INHERITS)
        )
        g.add_edge(
            GraphEdge(source="u.py::use", target="m.py::Base.m", kind=EdgeKind.CALLS)
        )
        r = ImpactAnalyzer(g).get_impact_radius("m.py::Child.m", depth=2)
        assert "u.py::use" in {n.id for n in r.nodes}
