"""Tests for CodeGraph indexing, mutation, and serialisation."""

from __future__ import annotations

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.graph.code_graph import CodeGraph


class TestCodeGraph:
    """CodeGraph resolution, edges, removal, serialisation."""

    @staticmethod
    def _node(
        nid: str,
        fp: str,
        name: str,
        qn: str,
        kind: NodeKind = NodeKind.FUNCTION,
    ) -> GraphNode:
        """Build a minimal graph node."""
        return GraphNode(
            id=nid,
            kind=kind,
            file_path=fp,
            start_line=1,
            end_line=2,
            name=name,
            qualified_name=qn,
        )

    def test_resolve_symbol_direct_id_and_unique_short_name(self) -> None:
        """Name that is already a node id resolves; unique short name resolves."""
        g = CodeGraph()
        a = self._node("m.py::foo", "m.py", "foo", "foo")
        b = self._node("m.py::bar", "m.py", "bar", "bar")
        g.add_node(a)
        g.add_node(b)
        assert g.resolve_symbol("m.py::foo") == "m.py::foo"
        assert g.resolve_symbol("bar") == "m.py::bar"

    def test_resolve_symbol_ambiguous_and_none(self) -> None:
        """Two symbols with same short name block resolution."""
        g = CodeGraph()
        g.add_node(self._node("a.py::dup", "a.py", "dup", "dup"))
        g.add_node(self._node("b.py::dup", "b.py", "dup", "dup"))
        assert g.has_ambiguous_symbol("dup")
        assert g.resolve_symbol("dup") is None

    def test_multi_kind_edges_on_same_pair(self) -> None:
        """Same (source, target) accumulates distinct edge kinds."""
        g = CodeGraph()
        g.add_node(self._node("m.py", "m.py", "m.py", "m.py", NodeKind.MODULE))
        g.add_node(self._node("m.py::f", "m.py", "f", "f"))
        g.add_node(self._node("t.py::g", "t.py", "g", "g"))
        g.add_edge(GraphEdge(source="m.py", target="t.py::g", kind=EdgeKind.IMPORTS))
        g.add_edge(GraphEdge(source="m.py", target="t.py::g", kind=EdgeKind.CALLS))
        assert g.edge_has_kind("m.py", "t.py::g", EdgeKind.IMPORTS)
        assert g.edge_has_kind("m.py", "t.py::g", EdgeKind.CALLS)
        g.remove_edge("m.py", "t.py::g", kind=EdgeKind.CALLS)
        assert g.edge_has_kind("m.py", "t.py::g", EdgeKind.IMPORTS)
        assert not g.edge_has_kind("m.py", "t.py::g", EdgeKind.CALLS)

    def test_remove_file_unindexes_nodes(self) -> None:
        """remove_file drops nodes and clears symbol/file indexes for that path."""
        g = CodeGraph()
        fp = "only.py"
        g.add_node(self._node(fp, fp, fp, fp, NodeKind.MODULE))
        g.add_node(self._node(f"{fp}::fn", fp, "fn", "fn"))
        assert g.resolve_symbol("fn") == f"{fp}::fn"
        n = g.remove_file(fp)
        assert n == 2
        assert g.resolve_symbol("fn") is None
        assert fp not in g.all_file_paths()

    def test_to_dict_from_dict_round_trip(self) -> None:
        """Serialisation preserves node ids and edge kinds (order-independent)."""
        g = CodeGraph()
        g.add_node(self._node("x.py", "x.py", "x.py", "x.py", NodeKind.MODULE))
        g.add_node(self._node("x.py::f", "x.py", "f", "f"))
        g.add_edge(GraphEdge(source="x.py", target="x.py::f", kind=EdgeKind.DEFINES))
        d = g.to_dict()
        g2 = CodeGraph.from_dict(d)
        assert {n["id"] for n in d["nodes"]} == {"x.py", "x.py::f"}
        edge_set = {(e["source"], e["target"], e["kind"]) for e in d["edges"]}
        assert edge_set == {("x.py", "x.py::f", "defines")}
        assert g2.node_count == g.node_count
        assert g2.edge_count == g.edge_count
