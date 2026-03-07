"""Tests for indexer.graph.code_graph."""

from indexer.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from indexer.graph.code_graph import CodeGraph


def _make_node(id, kind=NodeKind.MODULE, name=None):
    return GraphNode(
        id=id,
        kind=kind,
        file_path="f.py",
        start_line=1,
        end_line=1,
        name=name or id,
        qualified_name=id,
    )


def _make_edge(src, tgt, kind):
    return GraphEdge(source=src, target=tgt, kind=kind)


class TestCodeGraph:
    def test_add_and_get_node(self):
        g = CodeGraph()
        n = _make_node("a")
        g.add_node(n)
        assert g.get_node("a") == n
        assert g.node_count == 1

    def test_add_edge(self):
        g = CodeGraph()
        g.add_node(_make_node("a"))
        g.add_node(_make_node("b"))
        g.add_edge(_make_edge("a", "b", EdgeKind.IMPORTS))
        assert g.edge_count == 1

    def test_get_dependencies(self):
        g = CodeGraph()
        g.add_node(_make_node("a"))
        g.add_node(_make_node("b"))
        g.add_edge(_make_edge("a", "b", EdgeKind.IMPORTS))
        deps = g.get_dependencies("a")
        assert len(deps) == 1
        assert deps[0].id == "b"

    def test_get_dependents(self):
        g = CodeGraph()
        g.add_node(_make_node("a"))
        g.add_node(_make_node("b"))
        g.add_edge(_make_edge("a", "b", EdgeKind.IMPORTS))
        dependents = g.get_dependents("b")
        assert len(dependents) == 1
        assert dependents[0].id == "a"

    def test_get_callers_and_callees(self):
        g = CodeGraph()
        fn_a = _make_node("f::a", NodeKind.FUNCTION, "a")
        fn_b = _make_node("f::b", NodeKind.FUNCTION, "b")
        g.add_node(fn_a)
        g.add_node(fn_b)
        g.add_edge(_make_edge("f::a", "f::b", EdgeKind.CALLS))
        assert len(g.get_callees("f::a")) == 1
        assert len(g.get_callers("f::b")) == 1

    def test_get_subclasses(self):
        g = CodeGraph()
        g.add_node(_make_node("Base", NodeKind.CLASS, "Base"))
        g.add_node(_make_node("Child", NodeKind.CLASS, "Child"))
        g.add_edge(_make_edge("Child", "Base", EdgeKind.INHERITS))
        subs = g.get_subclasses("Base")
        assert len(subs) == 1
        assert subs[0].id == "Child"

    def test_get_definitions(self):
        g = CodeGraph()
        m = _make_node("mod", NodeKind.MODULE, "mod")
        fn = _make_node("mod::foo", NodeKind.FUNCTION, "foo")
        g.add_node(m)
        g.add_node(fn)
        g.add_edge(_make_edge("mod", "mod::foo", EdgeKind.DEFINES))
        defs = g.get_definitions("mod")
        assert len(defs) == 1

    def test_impact_radius(self):
        g = CodeGraph()
        for name in ["a", "b", "c"]:
            g.add_node(_make_node(name))
        g.add_edge(_make_edge("a", "b", EdgeKind.CALLS))
        g.add_edge(_make_edge("b", "c", EdgeKind.CALLS))
        impact = g.get_impact_radius("c", depth=2)
        ids = {n.id for n in impact}
        assert "b" in ids
        assert "a" in ids

    def test_shortest_path(self):
        g = CodeGraph()
        for name in ["a", "b", "c"]:
            g.add_node(_make_node(name))
        g.add_edge(_make_edge("a", "b", EdgeKind.CALLS))
        g.add_edge(_make_edge("b", "c", EdgeKind.CALLS))
        path = g.shortest_path("a", "c")
        assert len(path) == 3

    def test_shortest_path_no_path(self):
        g = CodeGraph()
        g.add_node(_make_node("a"))
        g.add_node(_make_node("z"))
        assert g.shortest_path("a", "z") == []

    def test_to_dict_and_from_dict(self):
        g = CodeGraph()
        g.add_node(_make_node("a"))
        g.add_node(_make_node("b"))
        g.add_edge(_make_edge("a", "b", EdgeKind.IMPORTS))
        d = g.to_dict()
        g2 = CodeGraph.from_dict(d)
        assert g2.node_count == 2
        assert g2.edge_count == 1

    def test_symbol_index_resolve(self):
        g = CodeGraph()
        g.add_node(_make_node("file.py::foo", NodeKind.FUNCTION, "foo"))
        g.add_node(_make_node("file.py::bar", NodeKind.FUNCTION, "bar"))
        g.add_edge(_make_edge("file.py::foo", "file.py::bar", EdgeKind.CALLS))
        callees = g.get_callees("foo")
        assert len(callees) == 1
        assert callees[0].name == "bar"

    def test_resolve_symbol_unique(self):
        g = CodeGraph()
        g.add_node(_make_node("a.py::MyClass", NodeKind.CLASS, "MyClass"))
        resolved = g.resolve_symbol("MyClass")
        assert resolved == "a.py::MyClass"

    def test_resolve_symbol_ambiguous_returns_none(self):
        g = CodeGraph()
        g.add_node(_make_node("a.py::foo", NodeKind.FUNCTION, "foo"))
        g.add_node(_make_node("b.py::foo", NodeKind.FUNCTION, "foo"))
        resolved = g.resolve_symbol("foo")
        assert resolved is None

    def test_resolve_edges_rewires_calls(self):
        g = CodeGraph()
        caller = _make_node("a.py::main", NodeKind.FUNCTION, "main")
        callee = _make_node("b.py::helper", NodeKind.FUNCTION, "helper")
        g.add_node(caller)
        g.add_node(callee)
        g.add_edge(_make_edge("a.py::main", "helper", EdgeKind.CALLS))

        resolved_count = g.resolve_edges()
        assert resolved_count == 1
        callees = g.get_callees("a.py::main")
        assert len(callees) == 1
        assert callees[0].id == "b.py::helper"

    def test_resolve_edges_ambiguous_kept(self):
        g = CodeGraph()
        g.add_node(_make_node("a.py::caller", NodeKind.FUNCTION, "caller"))
        g.add_node(_make_node("x.py::foo", NodeKind.FUNCTION, "foo"))
        g.add_node(_make_node("y.py::foo", NodeKind.FUNCTION, "foo"))
        g.add_edge(_make_edge("a.py::caller", "foo", EdgeKind.CALLS))

        resolved_count = g.resolve_edges()
        assert resolved_count == 0

    def test_nonexistent_node_returns_empty(self):
        g = CodeGraph()
        assert g.get_dependencies("nonexistent") == []
        assert g.get_callers("nonexistent") == []

    def test_remove_file(self):
        g = CodeGraph()
        mod_a = GraphNode(
            id="a.py",
            kind=NodeKind.MODULE,
            file_path="a.py",
            start_line=1,
            end_line=5,
            name="a.py",
            qualified_name="a.py",
        )
        fn = GraphNode(
            id="a.py::foo",
            kind=NodeKind.FUNCTION,
            file_path="a.py",
            start_line=1,
            end_line=2,
            name="foo",
            qualified_name="foo",
        )
        mod_b = GraphNode(
            id="b.py",
            kind=NodeKind.MODULE,
            file_path="b.py",
            start_line=1,
            end_line=1,
            name="b.py",
            qualified_name="b.py",
        )
        g.add_node(mod_a)
        g.add_node(fn)
        g.add_node(mod_b)
        g.add_edge(_make_edge("a.py", "a.py::foo", EdgeKind.DEFINES))

        removed = g.remove_file("a.py")
        assert removed == 2
        assert g.get_node("a.py") is None
        assert g.get_node("a.py::foo") is None
        assert g.get_node("b.py") is not None
        assert g.resolve_symbol("foo") is None
