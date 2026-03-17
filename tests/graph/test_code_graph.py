"""Tests for indexer.graph.code_graph."""

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, ImpactResult, NodeKind
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
        result = g.get_impact_radius("c", depth=2)
        assert isinstance(result, ImpactResult)
        ids = {n.id for n in result.nodes}
        assert "b" in ids
        assert "a" in ids
        assert result.resolved_node == "c"
        assert result.hint is None

    def test_impact_radius_excludes_defines(self):
        """DEFINES edges (containment) must not appear in impact results."""
        g = CodeGraph()
        module = _make_node("mod.py", NodeKind.MODULE, "mod.py")
        cls = _make_node("mod.py::Cls", NodeKind.CLASS, "Cls")
        method = _make_node("mod.py::Cls.run", NodeKind.FUNCTION, "run")
        caller = _make_node("other.py::main", NodeKind.FUNCTION, "main")

        for n in [module, cls, method, caller]:
            g.add_node(n)
        g.add_edge(_make_edge("mod.py", "mod.py::Cls", EdgeKind.DEFINES))
        g.add_edge(_make_edge("mod.py::Cls", "mod.py::Cls.run", EdgeKind.DEFINES))
        g.add_edge(_make_edge("other.py::main", "mod.py::Cls.run", EdgeKind.CALLS))

        result = g.get_impact_radius("mod.py::Cls.run", depth=2)
        ids = {n.id for n in result.nodes}
        assert "other.py::main" in ids
        assert "mod.py" not in ids, "module (via DEFINES) must be excluded"
        assert "mod.py::Cls" not in ids, "class (via DEFINES) must be excluded"

    def test_impact_radius_follows_imports(self):
        """IMPORTS edges should be followed in reverse traversal."""
        g = CodeGraph()
        g.add_node(_make_node("a.py"))
        g.add_node(_make_node("b.py"))
        g.add_edge(_make_edge("a.py", "b.py", EdgeKind.IMPORTS))

        result = g.get_impact_radius("b.py", depth=1)
        ids = {n.id for n in result.nodes}
        assert "a.py" in ids

    def test_impact_radius_follows_inherits(self):
        """INHERITS edges should be followed in reverse traversal."""
        g = CodeGraph()
        base = _make_node("a.py::Base", NodeKind.CLASS, "Base")
        child = _make_node("b.py::Child", NodeKind.CLASS, "Child")
        g.add_node(base)
        g.add_node(child)
        g.add_edge(_make_edge("b.py::Child", "a.py::Base", EdgeKind.INHERITS))

        result = g.get_impact_radius("a.py::Base", depth=1)
        ids = {n.id for n in result.nodes}
        assert "b.py::Child" in ids

    def test_impact_radius_not_found_returns_hint(self):
        """Querying a non-existent node returns diagnostics, not silent empty."""
        g = CodeGraph()
        g.add_node(_make_node("a.py::foo", NodeKind.FUNCTION, "foo"))

        result = g.get_impact_radius("a.py::does_not_exist")
        assert result.resolved_node is None
        assert result.nodes == []
        assert result.hint is not None
        assert "not in the graph" in result.hint

    def test_impact_radius_not_found_lists_available_nodes(self):
        """Hint includes available nodes in the same file when applicable."""
        g = CodeGraph()
        mod = GraphNode(
            id="svc.py", kind=NodeKind.MODULE, file_path="svc.py",
            start_line=1, end_line=10, name="svc.py", qualified_name="svc.py",
        )
        fn = GraphNode(
            id="svc.py::run", kind=NodeKind.FUNCTION, file_path="svc.py",
            start_line=2, end_line=5, name="run", qualified_name="run",
        )
        g.add_node(mod)
        g.add_node(fn)

        result = g.get_impact_radius("svc.py::missing")
        assert result.hint is not None
        assert "svc.py::run" in result.hint

    def test_impact_radius_no_callers(self):
        """Node exists but has no callers — empty results, no hint."""
        g = CodeGraph()
        g.add_node(_make_node("a.py::lonely", NodeKind.FUNCTION, "lonely"))

        result = g.get_impact_radius("a.py::lonely")
        assert result.resolved_node == "a.py::lonely"
        assert result.nodes == []
        assert result.hint is None

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

    # ------------------------------------------------------------------
    # Qualified index
    # ------------------------------------------------------------------

    def test_qualified_index_populated(self):
        g = CodeGraph()
        n = GraphNode(
            id="a.py::MyClass.method",
            kind=NodeKind.FUNCTION,
            file_path="a.py",
            start_line=5,
            end_line=10,
            name="method",
            qualified_name="MyClass.method",
        )
        g.add_node(n)
        assert "MyClass.method" in g._qualified_index
        assert "a.py::MyClass.method" in g._qualified_index["MyClass.method"]

    def test_resolve_symbol_via_qualified_name(self):
        g = CodeGraph()
        g.add_node(
            GraphNode(
                id="a.py::MyClass.run",
                kind=NodeKind.FUNCTION,
                file_path="a.py",
                start_line=1,
                end_line=5,
                name="run",
                qualified_name="MyClass.run",
            )
        )
        # "run" is ambiguous-possible but qualified name is unique
        assert g.resolve_symbol("MyClass.run") == "a.py::MyClass.run"

    def test_resolve_symbol_qualified_fallback_on_ambiguous_bare(self):
        """When bare name has multiple candidates, qualified name disambiguates."""
        g = CodeGraph()
        g.add_node(
            GraphNode(
                id="a.py::Foo.run",
                kind=NodeKind.FUNCTION,
                file_path="a.py",
                start_line=1,
                end_line=5,
                name="run",
                qualified_name="Foo.run",
            )
        )
        g.add_node(
            GraphNode(
                id="b.py::Bar.run",
                kind=NodeKind.FUNCTION,
                file_path="b.py",
                start_line=1,
                end_line=5,
                name="run",
                qualified_name="Bar.run",
            )
        )
        assert g.resolve_symbol("run") is None
        assert g.resolve_symbol("Foo.run") == "a.py::Foo.run"
        assert g.resolve_symbol("Bar.run") == "b.py::Bar.run"

    def test_qualified_index_cleaned_on_remove(self):
        g = CodeGraph()
        n = GraphNode(
            id="a.py::X.do",
            kind=NodeKind.FUNCTION,
            file_path="a.py",
            start_line=1,
            end_line=5,
            name="do",
            qualified_name="X.do",
        )
        g.add_node(n)
        assert g._qualified_index["X.do"] == {"a.py::X.do"}
        g.remove_file("a.py")
        assert "a.py::X.do" not in g._qualified_index.get("X.do", set())

    # ------------------------------------------------------------------
    # Phantom edge pruning
    # ------------------------------------------------------------------

    def test_prune_phantom_edges_removes_unresolvable(self):
        g = CodeGraph()
        caller = _make_node("a.py::main", NodeKind.FUNCTION, "main")
        g.add_node(caller)
        g.add_edge(_make_edge("a.py::main", "some_unknown_func", EdgeKind.CALLS))
        g.add_edge(_make_edge("a.py::main", "append", EdgeKind.CALLS))

        pruned = g.prune_phantom_edges()
        assert pruned == 2
        assert g.edge_count == 0

    def test_prune_phantom_edges_keeps_resolvable(self):
        g = CodeGraph()
        caller = _make_node("a.py::main", NodeKind.FUNCTION, "main")
        callee = _make_node("b.py::helper", NodeKind.FUNCTION, "helper")
        g.add_node(caller)
        g.add_node(callee)
        # Phantom target "helper" has a candidate in _symbol_index
        g.add_edge(_make_edge("a.py::main", "helper", EdgeKind.CALLS))
        # Truly unknown target
        g.add_edge(_make_edge("a.py::main", "no_such_thing", EdgeKind.CALLS))

        pruned = g.prune_phantom_edges()
        assert pruned == 1
        assert g.edge_count == 1

    def test_prune_removes_orphan_phantom_nodes(self):
        g = CodeGraph()
        caller = _make_node("a.py::main", NodeKind.FUNCTION, "main")
        g.add_node(caller)
        g.add_edge(_make_edge("a.py::main", "ghost", EdgeKind.CALLS))

        assert g.node_count == 2  # caller + phantom "ghost"
        g.prune_phantom_edges()
        assert g.node_count == 1  # only caller remains
