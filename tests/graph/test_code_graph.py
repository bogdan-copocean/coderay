"""Tests for indexer.graph.code_graph."""

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.graph.code_graph import CodeGraph


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

    def test_to_dict_and_from_dict(self):
        g = CodeGraph()
        g.add_node(_make_node("a"))
        g.add_node(_make_node("b"))
        g.add_edge(_make_edge("a", "b", EdgeKind.IMPORTS))
        d = g.to_dict()
        g2 = CodeGraph.from_dict(d)
        assert g2.node_count == 2
        assert g2.edge_count == 1

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

    def test_resolve_edges_ambiguous_kept(self):
        g = CodeGraph()
        g.add_node(_make_node("a.py::caller", NodeKind.FUNCTION, "caller"))
        g.add_node(_make_node("x.py::foo", NodeKind.FUNCTION, "foo"))
        g.add_node(_make_node("y.py::foo", NodeKind.FUNCTION, "foo"))
        g.add_edge(_make_edge("a.py::caller", "foo", EdgeKind.CALLS))

        resolved_count = g.resolve_edges()
        assert resolved_count == 0

    def test_resolve_edges_rewires_di_pattern(self):
        """When only one candidate exists, resolve_edges rewires both callers."""
        g = CodeGraph()
        impl = GraphNode(
            id="service/impl.py::ServiceImpl.do_work",
            kind=NodeKind.FUNCTION,
            file_path="service/impl.py",
            start_line=10,
            end_line=20,
            name="do_work",
            qualified_name="ServiceImpl.do_work",
        )
        internal = GraphNode(
            id="service/impl.py::ServiceImpl.run",
            kind=NodeKind.FUNCTION,
            file_path="service/impl.py",
            start_line=25,
            end_line=30,
            name="run",
            qualified_name="ServiceImpl.run",
        )
        api = GraphNode(
            id="api/handler.py::handle_request",
            kind=NodeKind.FUNCTION,
            file_path="api/handler.py",
            start_line=5,
            end_line=15,
            name="handle_request",
            qualified_name="handle_request",
        )
        g.add_node(impl)
        g.add_node(internal)
        g.add_node(api)
        g.add_edge(
            _make_edge("service/impl.py::ServiceImpl.run", "do_work", EdgeKind.CALLS)
        )
        g.add_edge(
            _make_edge("api/handler.py::handle_request", "do_work", EdgeKind.CALLS)
        )

        resolved = g.resolve_edges()
        assert resolved == 2

    def test_resolve_path_target(self):
        g = CodeGraph()
        mod = GraphNode(
            id="src/a/b/common/base.py",
            kind=NodeKind.MODULE,
            file_path="src/a/b/common/base.py",
            start_line=1,
            end_line=10,
            name="src/a/b/common/base.py",
            qualified_name="src/a/b/common/base.py",
        )
        g.add_node(mod)
        g.add_node(_make_node("src/x/file.py"))
        g.add_edge(_make_edge("src/x/file.py", "src/a/b/common/base", EdgeKind.IMPORTS))
        resolved = g.resolve_edges()
        assert resolved == 1

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

    def test_file_index_tracks_nodes(self):
        g = CodeGraph()
        mod = GraphNode(
            id="a.py",
            kind=NodeKind.MODULE,
            file_path="a.py",
            start_line=1,
            end_line=10,
            name="a.py",
            qualified_name="a.py",
        )
        fn1 = GraphNode(
            id="a.py::foo",
            kind=NodeKind.FUNCTION,
            file_path="a.py",
            start_line=1,
            end_line=5,
            name="foo",
            qualified_name="foo",
        )
        fn2 = GraphNode(
            id="a.py::bar",
            kind=NodeKind.FUNCTION,
            file_path="a.py",
            start_line=6,
            end_line=10,
            name="bar",
            qualified_name="bar",
        )
        other = GraphNode(
            id="b.py",
            kind=NodeKind.MODULE,
            file_path="b.py",
            start_line=1,
            end_line=1,
            name="b.py",
            qualified_name="b.py",
        )
        g.add_node(mod)
        g.add_node(fn1)
        g.add_node(fn2)
        g.add_node(other)

        assert g._file_index["a.py"] == {"a.py", "a.py::foo", "a.py::bar"}
        assert g._file_index["b.py"] == {"b.py"}

    def test_file_index_cleaned_after_remove(self):
        g = CodeGraph()
        mod = GraphNode(
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
            end_line=5,
            name="foo",
            qualified_name="foo",
        )
        g.add_node(mod)
        g.add_node(fn)
        assert "a.py" in g._file_index

        g.remove_file("a.py")
        assert "a.py" not in g._file_index

    def test_file_index_survives_roundtrip(self):
        g = CodeGraph()
        mod = GraphNode(
            id="a.py",
            kind=NodeKind.MODULE,
            file_path="a.py",
            start_line=1,
            end_line=5,
            name="a.py",
            qualified_name="a.py",
        )
        fn = GraphNode(
            id="a.py::calc",
            kind=NodeKind.FUNCTION,
            file_path="a.py",
            start_line=1,
            end_line=5,
            name="calc",
            qualified_name="calc",
        )
        g.add_node(mod)
        g.add_node(fn)

        data = g.to_dict()
        g2 = CodeGraph.from_dict(data)

        assert g2._file_index["a.py"] == {"a.py", "a.py::calc"}
        removed = g2.remove_file("a.py")
        assert removed == 2
        assert g2.node_count == 0
