"""Tests for graph.code_graph."""

import pytest

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, ImpactResult, NodeKind
from coderay.graph.code_graph import CodeGraph


def _make_node(id, kind=NodeKind.MODULE, name=None, file_path=None):
    return GraphNode(
        id=id,
        kind=kind,
        file_path=file_path or "f.py",
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
        assert "mod.py" not in ids
        assert "mod.py::Cls" not in ids

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

    def test_impact_radius_interface_aware_includes_interface_callers(self):
        """Querying implementation method includes callers typed against interface.

        Caller uses port: Port and calls port.save(). Edge goes to Port.save.
        Querying Impl.save (where Impl inherits Port) should find that caller.
        """
        g = CodeGraph()
        port_cls = GraphNode(
            id="ports.py::Port",
            kind=NodeKind.CLASS,
            file_path="ports.py",
            start_line=1,
            end_line=5,
            name="Port",
            qualified_name="Port",
        )
        port_method = GraphNode(
            id="ports.py::Port.save",
            kind=NodeKind.FUNCTION,
            file_path="ports.py",
            start_line=2,
            end_line=4,
            name="save",
            qualified_name="Port.save",
        )
        impl_cls = GraphNode(
            id="impl.py::Impl",
            kind=NodeKind.CLASS,
            file_path="impl.py",
            start_line=1,
            end_line=5,
            name="Impl",
            qualified_name="Impl",
        )
        impl_method = GraphNode(
            id="impl.py::Impl.save",
            kind=NodeKind.FUNCTION,
            file_path="impl.py",
            start_line=2,
            end_line=4,
            name="save",
            qualified_name="Impl.save",
        )
        caller = GraphNode(
            id="app.py::UseCase.execute",
            kind=NodeKind.FUNCTION,
            file_path="app.py",
            start_line=1,
            end_line=5,
            name="execute",
            qualified_name="UseCase.execute",
        )
        for n in [port_cls, port_method, impl_cls, impl_method, caller]:
            g.add_node(n)
        g.add_edge(_make_edge("impl.py::Impl", "ports.py::Port", EdgeKind.INHERITS))
        g.add_edge(
            _make_edge("app.py::UseCase.execute", "ports.py::Port.save", EdgeKind.CALLS)
        )

        result = g.get_impact_radius("impl.py::Impl.save", depth=2)
        ids = {n.id for n in result.nodes}
        assert "app.py::UseCase.execute" in ids

    def test_impact_radius_inherits_with_string_kind(self):
        """INHERITS edge with kind as string (e.g. from JSON) is still detected."""
        g = CodeGraph()
        base = _make_node("a.py::Base", NodeKind.CLASS, "Base")
        child = _make_node("b.py::Child", NodeKind.CLASS, "Child")
        g.add_node(base)
        g.add_node(child)
        g._g.add_edge("b.py::Child", "a.py::Base", kind="inherits")

        result = g.get_impact_radius("a.py::Base", depth=1)
        ids = {n.id for n in result.nodes}
        assert "b.py::Child" in ids

    def test_impact_radius_interface_aware_nested_parent_id(self):
        """Parent ID path::Module.Outer.Inner extracts Inner for fallback."""
        g = CodeGraph()
        inner_cls = GraphNode(
            id="ports.py::Module.Outer.Inner",
            kind=NodeKind.CLASS,
            file_path="ports.py",
            start_line=1,
            end_line=5,
            name="Inner",
            qualified_name="Module.Outer.Inner",
        )
        inner_method = GraphNode(
            id="ports.py::Module.Outer.Inner.save",
            kind=NodeKind.FUNCTION,
            file_path="ports.py",
            start_line=2,
            end_line=4,
            name="save",
            qualified_name="Module.Outer.Inner.save",
        )
        impl_cls = GraphNode(
            id="impl.py::Impl",
            kind=NodeKind.CLASS,
            file_path="impl.py",
            start_line=1,
            end_line=5,
            name="Impl",
            qualified_name="Impl",
        )
        impl_method = GraphNode(
            id="impl.py::Impl.save",
            kind=NodeKind.FUNCTION,
            file_path="impl.py",
            start_line=2,
            end_line=4,
            name="save",
            qualified_name="Impl.save",
        )
        caller = GraphNode(
            id="app.py::UseCase.execute",
            kind=NodeKind.FUNCTION,
            file_path="app.py",
            start_line=1,
            end_line=5,
            name="execute",
            qualified_name="UseCase.execute",
        )
        for n in [inner_cls, inner_method, impl_cls, impl_method, caller]:
            g.add_node(n)
        g.add_edge(
            _make_edge(
                "impl.py::Impl", "ports.py::Module.Outer.Inner", EdgeKind.INHERITS
            )
        )
        g.add_edge(
            _make_edge(
                "app.py::UseCase.execute",
                "ports.py::Module.Outer.Inner.save",
                EdgeKind.CALLS,
            )
        )

        result = g.get_impact_radius("impl.py::Impl.save", depth=2)
        ids = {n.id for n in result.nodes}
        assert "app.py::UseCase.execute" in ids

    def test_impact_radius_interface_aware_ambiguous_fallback_skipped(self):
        """When resolve_symbol is ambiguous for parent method, skip fallback gracefully."""
        g = CodeGraph()
        parent_cls = GraphNode(
            id="path::ports.Port",
            kind=NodeKind.CLASS,
            file_path="path/ports.py",
            start_line=1,
            end_line=5,
            name="Port",
            qualified_name="ports.Port",
        )
        port_a = GraphNode(
            id="a.py::Port.save",
            kind=NodeKind.FUNCTION,
            file_path="a.py",
            start_line=1,
            end_line=3,
            name="save",
            qualified_name="Port.save",
        )
        port_b = GraphNode(
            id="b.py::Port.save",
            kind=NodeKind.FUNCTION,
            file_path="b.py",
            start_line=1,
            end_line=3,
            name="save",
            qualified_name="Port.save",
        )
        impl_cls = GraphNode(
            id="impl.py::Impl",
            kind=NodeKind.CLASS,
            file_path="impl.py",
            start_line=1,
            end_line=5,
            name="Impl",
            qualified_name="Impl",
        )
        impl_method = GraphNode(
            id="impl.py::Impl.save",
            kind=NodeKind.FUNCTION,
            file_path="impl.py",
            start_line=2,
            end_line=4,
            name="save",
            qualified_name="Impl.save",
        )
        caller_direct = GraphNode(
            id="app.py::direct_caller",
            kind=NodeKind.FUNCTION,
            file_path="app.py",
            start_line=1,
            end_line=5,
            name="direct_caller",
            qualified_name="direct_caller",
        )
        for n in [parent_cls, port_a, port_b, impl_cls, impl_method, caller_direct]:
            g.add_node(n)
        g.add_edge(_make_edge("impl.py::Impl", "path::ports.Port", EdgeKind.INHERITS))
        g.add_edge(
            _make_edge("app.py::direct_caller", "impl.py::Impl.save", EdgeKind.CALLS)
        )

        result = g.get_impact_radius("impl.py::Impl.save", depth=2)
        ids = {n.id for n in result.nodes}
        assert "app.py::direct_caller" in ids

    def test_impact_radius_not_found_returns_hint(self):
        g = CodeGraph()
        g.add_node(_make_node("a.py::foo", NodeKind.FUNCTION, "foo"))

        result = g.get_impact_radius("a.py::does_not_exist")
        assert result.resolved_node is None
        assert result.nodes == []
        assert result.hint is not None
        assert "not in the graph" in result.hint

    def test_impact_radius_not_found_lists_available_nodes(self):
        g = CodeGraph()
        mod = GraphNode(
            id="svc.py",
            kind=NodeKind.MODULE,
            file_path="svc.py",
            start_line=1,
            end_line=10,
            name="svc.py",
            qualified_name="svc.py",
        )
        fn = GraphNode(
            id="svc.py::run",
            kind=NodeKind.FUNCTION,
            file_path="svc.py",
            start_line=2,
            end_line=5,
            name="run",
            qualified_name="run",
        )
        g.add_node(mod)
        g.add_node(fn)

        result = g.get_impact_radius("svc.py::missing")
        assert result.hint is not None
        assert "svc.py::run" in result.hint

    def test_impact_radius_no_callers_no_imports(self):
        """Zero callers on an unimported module gives a 'not imported' hint."""
        g = CodeGraph()
        g.add_node(_make_node("a.py::lonely", NodeKind.FUNCTION, "lonely"))

        result = g.get_impact_radius("a.py::lonely")
        assert result.resolved_node == "a.py::lonely"
        assert result.nodes == []
        assert result.hint is not None
        assert "not imported" in result.hint

    def test_impact_radius_no_callers_module_imported(self):
        """Zero callers but module is imported gives an informative hint."""
        g = CodeGraph()
        mod = _make_node("svc.py", NodeKind.MODULE, "svc.py", file_path="svc.py")
        method = GraphNode(
            id="svc.py::Service.run",
            kind=NodeKind.FUNCTION,
            file_path="svc.py",
            start_line=5,
            end_line=10,
            name="run",
            qualified_name="Service.run",
        )
        importer = _make_node(
            "app.py::main", NodeKind.FUNCTION, "main", file_path="app.py"
        )
        g.add_node(mod)
        g.add_node(method)
        g.add_node(importer)
        g.add_edge(_make_edge("app.py::main", "svc.py", EdgeKind.IMPORTS))

        result = g.get_impact_radius("svc.py::Service.run")
        assert result.resolved_node == "svc.py::Service.run"
        assert result.nodes == []
        assert result.hint is not None
        assert "imported by 1 file(s)" in result.hint

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

        assert g._file_index["a.py"] == {
            "a.py",
            "a.py::foo",
            "a.py::bar",
        }
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
        assert g.resolve_symbol("MyClass.run") == "a.py::MyClass.run"

    def test_resolve_symbol_qualified_fallback_on_ambiguous_bare(self):
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
    # Helper methods used by builder
    # ------------------------------------------------------------------

    def test_remove_edge(self):
        g = CodeGraph()
        g.add_node(_make_node("a"))
        g.add_node(_make_node("b"))
        g.add_edge(_make_edge("a", "b", EdgeKind.CALLS))
        assert g.edge_count == 1
        g.remove_edge("a", "b")
        assert g.edge_count == 0

    def test_has_symbol_candidates(self):
        g = CodeGraph()
        g.add_node(_make_node("a.py::helper", NodeKind.FUNCTION, "helper"))
        assert g.has_symbol_candidates("helper") is True
        assert g.has_symbol_candidates("nonexistent") is False

    def test_all_file_paths(self):
        g = CodeGraph()
        g.add_node(
            GraphNode(
                id="a.py",
                kind=NodeKind.MODULE,
                file_path="a.py",
                start_line=1,
                end_line=5,
                name="a.py",
                qualified_name="a.py",
            )
        )
        g.add_node(
            GraphNode(
                id="b.py",
                kind=NodeKind.MODULE,
                file_path="b.py",
                start_line=1,
                end_line=5,
                name="b.py",
                qualified_name="b.py",
            )
        )
        assert g.all_file_paths() == {"a.py", "b.py"}

    def test_remove_orphan_phantoms(self):
        g = CodeGraph()
        caller = _make_node("a.py::main", NodeKind.FUNCTION, "main")
        g.add_node(caller)
        g.add_edge(_make_edge("a.py::main", "ghost", EdgeKind.CALLS))
        assert g.node_count == 2

        g.remove_edge("a.py::main", "ghost")
        g.remove_orphan_phantoms()
        assert g.node_count == 1

    # ------------------------------------------------------------------
    # Fuzzy resolution
    # ------------------------------------------------------------------

    def test_fuzzy_resolve_single_match(self):
        """Fuzzy resolve succeeds when method name matches one node in file."""
        g = CodeGraph()
        g.add_node(
            GraphNode(
                id="svc.py::ActualClass.run",
                kind=NodeKind.FUNCTION,
                file_path="svc.py",
                start_line=5,
                end_line=10,
                name="run",
                qualified_name="ActualClass.run",
            )
        )

        result = g.get_impact_radius("svc.py::WrongClass.run")
        assert result.resolved_node == "svc.py::ActualClass.run"
        assert result.resolution_warning is not None
        assert "WrongClass.run" in result.resolution_warning
        assert "ActualClass.run" in result.resolution_warning

    def test_fuzzy_resolve_multiple_matches_falls_back(self):
        """Fuzzy resolve falls back to not-found when multiple methods match."""
        g = CodeGraph()
        g.add_node(
            GraphNode(
                id="svc.py::ClassA.run",
                kind=NodeKind.FUNCTION,
                file_path="svc.py",
                start_line=5,
                end_line=10,
                name="run",
                qualified_name="ClassA.run",
            )
        )
        g.add_node(
            GraphNode(
                id="svc.py::ClassB.run",
                kind=NodeKind.FUNCTION,
                file_path="svc.py",
                start_line=15,
                end_line=20,
                name="run",
                qualified_name="ClassB.run",
            )
        )

        result = g.get_impact_radius("svc.py::WrongClass.run")
        assert result.resolved_node is None
        assert result.hint is not None

    def test_fuzzy_resolve_preserves_not_found_for_total_miss(self):
        """When nothing matches, the existing hint with available nodes is shown."""
        g = CodeGraph()
        g.add_node(
            GraphNode(
                id="svc.py::Service.run",
                kind=NodeKind.FUNCTION,
                file_path="svc.py",
                start_line=5,
                end_line=10,
                name="run",
                qualified_name="Service.run",
            )
        )

        result = g.get_impact_radius("svc.py::Totally.different")
        assert result.resolved_node is None
        assert result.hint is not None
        assert "svc.py::Service.run" in result.hint

    @pytest.mark.parametrize(
        "resolution_warning,expected_key,expected_val",
        [
            ("Resolved from 'Baz.bar'", True, "Resolved from 'Baz.bar'"),
            (None, False, None),
        ],
    )
    def test_resolution_warning_in_to_dict(
        self, resolution_warning, expected_key, expected_val
    ):
        result = ImpactResult(
            resolved_node="a.py::Foo.bar",
            nodes=[],
            resolution_warning=resolution_warning,
        )
        d = result.to_dict()
        assert ("resolution_warning" in d) == expected_key
        if expected_key:
            assert d["resolution_warning"] == expected_val

    # ------------------------------------------------------------------
    # Bare-name phantom deduplication (common method names)
    # ------------------------------------------------------------------

    def test_bare_name_targets_excluded_when_method_name_ambiguous(self):
        """Querying a method with overloaded name (get, post) does not include bare phantom callers.

        When multiple nodes share the same name (e.g. many classes have .get),
        the bare phantom 'get' aggregates callers of all of them. Including it
        would produce massive false positives. We only use bare name when unique.
        """
        g = CodeGraph()
        resource_a = GraphNode(
            id="api.py::ResourceA.get",
            kind=NodeKind.FUNCTION,
            file_path="api.py",
            start_line=1,
            end_line=5,
            name="get",
            qualified_name="ResourceA.get",
        )
        resource_b = GraphNode(
            id="api.py::ResourceB.get",
            kind=NodeKind.FUNCTION,
            file_path="api.py",
            start_line=10,
            end_line=15,
            name="get",
            qualified_name="ResourceB.get",
        )
        unrelated_caller = _make_node(
            "tests.py::test_s3_get",
            NodeKind.FUNCTION,
            "test_s3_get",
            file_path="tests.py",
        )
        g.add_node(resource_a)
        g.add_node(resource_b)
        g.add_node(unrelated_caller)
        g.add_edge(_make_edge("tests.py::test_s3_get", "get", EdgeKind.CALLS))

        result = g.get_impact_radius("api.py::ResourceA.get", depth=2)
        ids = {n.id for n in result.nodes}
        assert "tests.py::test_s3_get" not in ids

    def test_bare_name_targets_included_when_method_name_unique(self):
        """Querying a method with unique name includes callers of the bare phantom.

        DI-style calls like processor.delete_user_async() create edges to the
        bare name. When that name is unique, we correctly attribute those callers.
        """
        g = CodeGraph()
        method = GraphNode(
            id="svc.py::UserService.delete_user_async",
            kind=NodeKind.FUNCTION,
            file_path="svc.py",
            start_line=1,
            end_line=5,
            name="delete_user_async",
            qualified_name="UserService.delete_user_async",
        )
        caller = _make_node(
            "views.py::handle_delete",
            NodeKind.FUNCTION,
            "handle_delete",
            file_path="views.py",
        )
        g.add_node(method)
        g.add_node(caller)
        g.add_edge(
            _make_edge("views.py::handle_delete", "delete_user_async", EdgeKind.CALLS)
        )

        result = g.get_impact_radius("svc.py::UserService.delete_user_async", depth=2)
        ids = {n.id for n in result.nodes}
        assert "views.py::handle_delete" in ids

    # ------------------------------------------------------------------
    # B3: own-module exclusion from impact_radius results
    # ------------------------------------------------------------------

    def test_impact_radius_excludes_own_module(self):
        """The queried symbol's own module node must not appear in results."""
        g = CodeGraph()
        module = GraphNode(
            id="svc.py",
            kind=NodeKind.MODULE,
            file_path="svc.py",
            start_line=1,
            end_line=50,
            name="svc.py",
            qualified_name="svc.py",
        )
        method = GraphNode(
            id="svc.py::Service.run",
            kind=NodeKind.FUNCTION,
            file_path="svc.py",
            start_line=5,
            end_line=10,
            name="run",
            qualified_name="Service.run",
        )
        caller = GraphNode(
            id="app.py::main",
            kind=NodeKind.FUNCTION,
            file_path="app.py",
            start_line=1,
            end_line=5,
            name="main",
            qualified_name="main",
        )
        for n in [module, method, caller]:
            g.add_node(n)
        g.add_edge(_make_edge("app.py::main", "svc.py::Service.run", EdgeKind.CALLS))
        g.add_edge(_make_edge("app.py::main", "svc.py", EdgeKind.IMPORTS))

        result = g.get_impact_radius("svc.py::Service.run", depth=2)
        ids = {n.id for n in result.nodes}
        assert "app.py::main" in ids
        assert "svc.py" not in ids, "own module should be excluded"

    # ------------------------------------------------------------------
    # has_ambiguous_symbol
    # ------------------------------------------------------------------

    def test_has_ambiguous_symbol_true(self):
        g = CodeGraph()
        g.add_node(_make_node("a.py::foo", NodeKind.FUNCTION, "foo", file_path="a.py"))
        g.add_node(_make_node("b.py::foo", NodeKind.FUNCTION, "foo", file_path="b.py"))
        assert g.has_ambiguous_symbol("foo") is True

    def test_has_ambiguous_symbol_false_for_unique(self):
        g = CodeGraph()
        g.add_node(_make_node("a.py::unique_fn", NodeKind.FUNCTION, "unique_fn"))
        assert g.has_ambiguous_symbol("unique_fn") is False

    def test_has_ambiguous_symbol_false_for_missing(self):
        g = CodeGraph()
        assert g.has_ambiguous_symbol("nonexistent") is False
