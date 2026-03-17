"""Comprehensive graph extraction tests against a realistic Python sample.

Covers all implemented features (imports, definitions, calls, inheritance,
assignments, instance tracking, filtering) and marks known gaps with xfail
so progress is visible as the extractor improves.
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


@pytest.fixture
def nodes(graph):
    return graph[0]


@pytest.fixture
def edges(graph):
    return graph[1]


# -- helpers ---------------------------------------------------------------


def _edge_targets(edges, kind: EdgeKind) -> set[str]:
    return {e.target for e in edges if e.kind == kind}


def _edge_sources(edges, kind: EdgeKind) -> set[str]:
    return {e.source for e in edges if e.kind == kind}


def _edges_of(edges, kind: EdgeKind):
    return [e for e in edges if e.kind == kind]


def _calls_from(edges, source_fragment: str) -> set[str]:
    """CALLS targets where source contains *source_fragment*."""
    return {
        e.target
        for e in edges
        if e.kind == EdgeKind.CALLS and source_fragment in e.source
    }


def _node_names(nodes, kind: NodeKind) -> set[str]:
    return {n.name for n in nodes if n.kind == kind}


def _qualified_names(nodes, kind: NodeKind) -> set[str]:
    return {n.qualified_name for n in nodes if n.kind == kind}


# =========================================================================
#  1. IMPORTS
# =========================================================================


class TestImports:
    """Verify all import variants produce correct IMPORTS edges."""

    def test_bare_imports_captured(self, edges):
        targets = _edge_targets(edges, EdgeKind.IMPORTS)
        assert "os" in targets
        assert "sys" in targets

    def test_from_imports_captured(self, edges):
        targets = _edge_targets(edges, EdgeKind.IMPORTS)
        assert "pathlib::Path" in targets
        assert "collections::defaultdict" in targets

    def test_aliased_import_uses_original_name(self, edges):
        """``import math as m`` should produce target 'math', not 'm'."""
        targets = _edge_targets(edges, EdgeKind.IMPORTS)
        assert "math" in targets
        assert "m" not in targets

    def test_aliased_from_import_uses_original_name(self, edges):
        """``from collections import defaultdict as dd`` → target has original."""
        targets = _edge_targets(edges, EdgeKind.IMPORTS)
        assert "collections::defaultdict" in targets

    def test_excluded_module_no_import_edge(self, edges):
        """Imports from typing / abc / __future__ should not appear."""
        targets = _edge_targets(edges, EdgeKind.IMPORTS)
        assert not any(t.startswith("typing::") for t in targets)
        assert not any(t.startswith("abc::") for t in targets)
        assert "__future__" not in targets

    def test_multiple_from_imports_captured(self, edges):
        """``from typing import Any, Optional`` — both still resolve (no edge)."""
        targets = _edge_targets(edges, EdgeKind.IMPORTS)
        assert "typing::Any" not in targets
        assert "typing::Optional" not in targets

    def test_non_excluded_module_import_present(self, edges):
        targets = _edge_targets(edges, EdgeKind.IMPORTS)
        assert "os" in targets
        assert "pathlib::Path" in targets


# =========================================================================
#  2. DEFINITIONS — nodes and DEFINES edges
# =========================================================================


class TestDefinitions:
    """Verify function and class nodes are created with correct qualified names."""

    def test_all_classes_found(self, nodes):
        names = _node_names(nodes, NodeKind.CLASS)
        expected = {
            "Animal",
            "Dog",
            "GuideDog",
            "HttpClient",
            "Service",
            "DecoratedClass",
            "Config",
            "Outer",
            "Inner",
        }
        assert expected.issubset(names)

    def test_all_top_level_functions_found(self, nodes):
        names = _node_names(nodes, NodeKind.FUNCTION)
        for fn in (
            "my_decorator",
            "decorated_func",
            "use_aliases",
            "instance_tracking_example",
            "chained_access_example",
            "lambda_and_comprehension_example",
            "math_usage_example",
            "call_shadowed_len",
            "call_real_builtins",
        ):
            assert fn in names, f"missing function node: {fn}"

    def test_nested_function_found(self, nodes):
        qualified = _qualified_names(nodes, NodeKind.FUNCTION)
        assert "my_decorator.wrapper" in qualified

    def test_method_qualified_names(self, nodes):
        qualified = _qualified_names(nodes, NodeKind.FUNCTION)
        assert "Animal.speak" in qualified
        assert "Dog.bark" in qualified
        assert "Service.fetch" in qualified

    def test_defines_edges_link_module_to_top_level(self, nodes, edges):
        """Module DEFINES edges point to top-level classes and functions only."""
        pg = str(SAMPLE_PATH)
        module_defines = [e for e in edges if e.kind == EdgeKind.DEFINES and e.source == pg]
        targets = {e.target for e in module_defines}
        assert any(f"{pg}::Animal" in t for t in targets)
        assert any(f"{pg}::Dog" in t for t in targets)
        assert any("my_decorator" in t for t in targets)

    def test_defines_edges_hierarchical_for_methods(self, edges):
        """Methods are defined by their class, not the module."""
        pg = str(SAMPLE_PATH)
        class_defines = [
            e for e in edges
            if e.kind == EdgeKind.DEFINES and e.source == f"{pg}::Animal"
        ]
        targets = {e.target for e in class_defines}
        assert f"{pg}::Animal.speak" in targets
        assert f"{pg}::Animal.move" in targets
        assert f"{pg}::Animal._walk" in targets

    def test_defines_edges_hierarchical_for_nested_class(self, edges):
        """Nested class is defined by the outer class, not the module."""
        pg = str(SAMPLE_PATH)
        outer_defines = [
            e for e in edges
            if e.kind == EdgeKind.DEFINES and e.source == f"{pg}::Outer"
        ]
        targets = {e.target for e in outer_defines}
        assert f"{pg}::Outer.Inner" in targets

    def test_defines_edges_hierarchical_for_nested_class_method(self, edges):
        """Inner class method is defined by Inner, not Outer or the module."""
        pg = str(SAMPLE_PATH)
        inner_defines = [
            e for e in edges
            if e.kind == EdgeKind.DEFINES and e.source == f"{pg}::Outer.Inner"
        ]
        targets = {e.target for e in inner_defines}
        assert f"{pg}::Outer.Inner.inner_method" in targets

    def test_inner_class_qualified_name(self, nodes):
        qualified = _qualified_names(nodes, NodeKind.CLASS)
        assert "Outer.Inner" in qualified

    def test_inner_class_method_qualified_name(self, nodes):
        qualified = _qualified_names(nodes, NodeKind.FUNCTION)
        assert "Outer.Inner.inner_method" in qualified


# =========================================================================
#  3. INHERITS
# =========================================================================


class TestInheritance:
    """Verify INHERITS edges resolve base classes correctly."""

    def test_local_inheritance_resolved(self, edges):
        """Dog(Animal) should resolve to the local Animal definition."""
        inherits = _edges_of(edges, EdgeKind.INHERITS)
        dog_inherits = [
            e for e in inherits if "Dog" in e.source and "GuideDog" not in e.source
        ]
        targets = {e.target for e in dog_inherits}
        assert any("::Animal" in t for t in targets), (
            f"Dog INHERITS should resolve to local Animal. Got: {targets}"
        )

    def test_imported_base_class_resolved(self, edges):
        """GuideDog(Dog, ABC) — ABC should resolve through import."""
        inherits = _edges_of(edges, EdgeKind.INHERITS)
        guide_inherits = [e for e in inherits if "GuideDog" in e.source]
        targets = {e.target for e in guide_inherits}
        assert any("abc::ABC" in t for t in targets), (
            f"GuideDog INHERITS should include abc::ABC. Got: {targets}"
        )

    def test_multiple_inheritance_creates_multiple_edges(self, edges):
        inherits = _edges_of(edges, EdgeKind.INHERITS)
        guide_inherits = [e for e in inherits if "GuideDog" in e.source]
        assert len(guide_inherits) == 2, (
            f"GuideDog has 2 bases, expected 2 INHERITS edges. Got {len(guide_inherits)}"
        )


# =========================================================================
#  4. CALLS — direct, self, instance, aliased
# =========================================================================


class TestCalls:
    """Verify CALLS edges are created and resolved correctly."""

    def test_self_method_call_resolves(self, edges):
        """self.bark() inside Dog.speak → Dog.bark."""
        pg = str(SAMPLE_PATH)
        targets = _calls_from(edges, "Dog.speak")
        assert f"{pg}::Dog.bark" in targets

    def test_self_private_method_call_resolves(self, edges):
        """self._walk() inside Animal.move → Animal._walk."""
        pg = str(SAMPLE_PATH)
        targets = _calls_from(edges, "Animal.move")
        assert f"{pg}::Animal._walk" in targets

    def test_self_bootstrap_calls_resolve(self, edges):
        """self._setup_logging() and self._connect() inside Service.bootstrap."""
        pg = str(SAMPLE_PATH)
        targets = _calls_from(edges, "Service.bootstrap")
        assert f"{pg}::Service._setup_logging" in targets
        assert f"{pg}::Service._connect" in targets

    def test_instance_method_call_resolved(self, edges):
        """client = HttpClient(); client.get() → resolves to HttpClient.get."""
        targets = _calls_from(edges, "instance_tracking_example")
        pg = str(SAMPLE_PATH)
        assert f"{pg}::HttpClient.get" in targets

    def test_instance_post_call_resolved(self, edges):
        """client.post() in instance_tracking_example → HttpClient.post."""
        targets = _calls_from(edges, "instance_tracking_example")
        pg = str(SAMPLE_PATH)
        assert f"{pg}::HttpClient.post" in targets

    def test_module_level_instance_method_resolved(self, edges):
        """service.fetch('/health') at module level → Service.fetch."""
        pg = str(SAMPLE_PATH)
        module_calls = _calls_from(edges, pg)
        unscoped = {t for t in module_calls if "::" not in t or pg in t}
        assert any("Service.fetch" in t for t in module_calls), (
            f"Expected Service.fetch in module-level calls. Got: {module_calls}"
        )

    def test_aliased_call_resolved(self, edges):
        """dd(int) in use_aliases resolves to collections::defaultdict."""
        targets = _calls_from(edges, "use_aliases")
        assert "collections::defaultdict" in targets

    def test_locally_defined_function_call_resolved(self, edges):
        """call_shadowed_len() calls len() which is locally defined."""
        pg = str(SAMPLE_PATH)
        targets = _calls_from(edges, "call_shadowed_len")
        assert any("len" in t for t in targets), (
            f"Locally-defined len should be callable. Got: {targets}"
        )


# =========================================================================
#  5. ASSIGNMENTS and ALIASES
# =========================================================================


class TestAssignments:
    """Verify alias tracking via assignments."""

    def test_alias_to_from_import_resolves_on_call(self, edges):
        """my_dd = dd; my_dd(int) → collections::defaultdict."""
        targets = _calls_from(edges, "use_aliases")
        assert "collections::defaultdict" in targets

    def test_alias_to_class_resolves_on_call(self, edges):
        """client_class = HttpClient; client_class() → HttpClient."""
        targets = _calls_from(edges, "use_aliases")
        pg = str(SAMPLE_PATH)
        assert any("HttpClient" in t for t in targets), (
            f"Expected HttpClient via alias. Got: {targets}"
        )

    def test_alias_to_bare_import_resolves_on_call(self, edges):
        """path_func = Path; path_func('.') → pathlib::Path."""
        targets = _calls_from(edges, "use_aliases")
        assert "pathlib::Path" in targets


# =========================================================================
#  6. MODULE FILTERING
# =========================================================================


class TestModuleFiltering:
    """Verify excluded modules and builtins are filtered from the graph."""

    def test_builtin_calls_filtered(self, edges):
        """print, isinstance, range should not appear as CALLS targets."""
        targets = _calls_from(edges, "call_real_builtins")
        for name in ("print", "isinstance", "range"):
            assert name not in targets, f"builtin {name} should be filtered"

    def test_excluded_import_still_resolves_calls(self, edges):
        """ABC is from abc (excluded), but resolution should still work."""
        inherits = _edges_of(edges, EdgeKind.INHERITS)
        guide_inherits = [e for e in inherits if "GuideDog" in e.source]
        targets = {e.target for e in guide_inherits}
        assert any("abc::ABC" in t for t in targets)

    def test_shadowed_builtin_not_filtered(self, edges):
        """Project-defined len() should NOT be filtered."""
        pg = str(SAMPLE_PATH)
        targets = _calls_from(edges, "call_shadowed_len")
        assert any("len" in t for t in targets)


# =========================================================================
#  7. DECORATED DEFINITIONS
# =========================================================================


class TestDecoratedDefinitions:
    """Decorated functions/classes should still produce correct nodes."""

    def test_decorated_function_node_exists(self, nodes):
        names = _node_names(nodes, NodeKind.FUNCTION)
        assert "decorated_func" in names

    def test_decorated_class_node_exists(self, nodes):
        names = _node_names(nodes, NodeKind.CLASS)
        assert "DecoratedClass" in names

    def test_decorated_class_method_exists(self, nodes):
        qualified = _qualified_names(nodes, NodeKind.FUNCTION)
        assert "DecoratedClass.method" in qualified

    @pytest.mark.xfail(reason="TODO: emit DECORATES edges for decorated definitions")
    def test_decorates_edge_emitted(self, edges):
        """@my_decorator on decorated_func should emit a DECORATES edge."""
        decorates = [e for e in edges if e.kind.value == "decorates"]
        assert len(decorates) > 0


# =========================================================================
#  8. KNOWN GAPS — xfail tests that document missing features
# =========================================================================


class TestWorkingEdgeCases:
    """Features that were previously gaps but now work correctly."""

    def test_static_method_call_at_module_level(self, edges):
        """Config.from_env() at module level resolves via FileContext."""
        pg = str(SAMPLE_PATH)
        module_calls = _calls_from(edges, pg)
        assert f"{pg}::Config.from_env" in module_calls

    def test_nested_class_instantiation_via_self(self, edges):
        """self.Inner() in Outer.use_inner resolves to Outer.Inner."""
        pg = str(SAMPLE_PATH)
        targets = _calls_from(edges, "Outer.use_inner")
        assert any("Outer.Inner" in t for t in targets)


class TestKnownGaps:
    """Tests for features documented as TODOs in the extractor.

    Each test is marked xfail so CI stays green while gaps are visible.
    When a gap is fixed, the xfail will start passing and pytest will
    report it as xpass, signaling the marker should be removed.
    """

    @pytest.mark.xfail(
        reason="TODO: self.client = HttpClient() → self.client.get() resolution"
    )
    def test_composition_via_self_attribute(self, edges):
        """Service.__init__ sets self.client = HttpClient();
        Service.fetch calls self.client.get() — should resolve to HttpClient.get.
        """
        pg = str(SAMPLE_PATH)
        targets = _calls_from(edges, "Service.fetch")
        assert f"{pg}::HttpClient.get" in targets

    @pytest.mark.xfail(
        reason="TODO: deep chained attribute resolution via type inference"
    )
    def test_deep_chained_access_resolved(self, edges):
        """service.client.get('/deep') should resolve to HttpClient.get."""
        pg = str(SAMPLE_PATH)
        targets = _calls_from(edges, "chained_access_example")
        assert f"{pg}::HttpClient.get" in targets

    @pytest.mark.xfail(reason="TODO: lambda/comprehension scope attribution")
    def test_lambda_call_attributed_to_lambda_scope(self, edges):
        """abs() inside a lambda should be attributed to the lambda, not
        the enclosing function.  Currently attributed to the parent."""
        calls = _edges_of(edges, EdgeKind.CALLS)
        lambda_calls = [e for e in calls if "lambda" in e.source.lower()]
        assert len(lambda_calls) > 0

    @pytest.mark.xfail(reason="TODO: handle wildcard imports")
    def test_wildcard_import(self):
        """``from os.path import *`` should register all exported names."""
        code = "from os.path import *\njoin('a', 'b')\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "os/path::join" in targets or "os.path::join" in targets

    @pytest.mark.xfail(reason="TODO: tuple unpacking in assignments")
    def test_tuple_unpacking_alias(self):
        """a, b = func() — calling a() should not produce a bare 'a' target."""
        code = "from module import get_pair\na, b = get_pair()\na()\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "a" not in targets, (
            "Bare 'a' target means tuple unpacking was not tracked"
        )


# =========================================================================
#  9. PRINT GRAPH — manual inspection helper
# =========================================================================


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
