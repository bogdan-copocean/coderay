"""Tests for DefinitionHandlerMixin: DEFINES, INHERITS edges, nodes.

Covers: function/class nodes, DEFINES hierarchy, INHERITS resolution,
@property detection, typed parameters for param injection.
"""

from pathlib import Path

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.extractor import extract_graph_from_file

SAMPLE_PATH = Path(__file__).parent.parent / "graph_sample.py"


def _node_names(nodes, kind: NodeKind):
    return {n.name for n in nodes if n.kind == kind}


def _qualified_names(nodes, kind: NodeKind):
    return {n.qualified_name for n in nodes if n.kind == kind}


def _edges_of(edges, kind: EdgeKind):
    return [e for e in edges if e.kind == kind]


# ---------------------------------------------------------------------------
# _handle_function_def: FUNCTION nodes, DEFINES edges
# ---------------------------------------------------------------------------


class TestFunctionDefinitions:
    """Function nodes and DEFINES edges."""

    def test_top_level_function_node(self):
        code = "def helper():\n    pass\n"
        nodes, _ = extract_graph_from_file("test.py", code)
        names = _node_names(nodes, NodeKind.FUNCTION)
        assert "helper" in names

    def test_function_qualified_name(self):
        code = "def my_func():\n    pass\n"
        nodes, _ = extract_graph_from_file("test.py", code)
        qualified = _qualified_names(nodes, NodeKind.FUNCTION)
        assert "my_func" in qualified

    def test_method_qualified_name_includes_class(self):
        code = "class Dog:\n    def bark(self):\n        pass\n"
        nodes, _ = extract_graph_from_file("test.py", code)
        qualified = _qualified_names(nodes, NodeKind.FUNCTION)
        assert "Dog.bark" in qualified

    def test_nested_function_qualified_name(self):
        code = "def outer():\n    def inner():\n        pass\n"
        nodes, _ = extract_graph_from_file("test.py", code)
        qualified = _qualified_names(nodes, NodeKind.FUNCTION)
        assert "outer.inner" in qualified

    def test_module_defines_top_level_function(self):
        code = "def helper():\n    pass\n"
        _, edges = extract_graph_from_file("test.py", code)
        defines = _edges_of(edges, EdgeKind.DEFINES)
        module_defines = [e for e in defines if e.source == "test.py"]
        assert any("helper" in e.target for e in module_defines)

    def test_class_defines_method(self):
        code = "class Dog:\n    def bark(self):\n        pass\n"
        _, edges = extract_graph_from_file("test.py", code)
        defines = _edges_of(edges, EdgeKind.DEFINES)
        class_defines = [e for e in defines if "Dog" in e.source and "bark" in e.target]
        assert len(class_defines) >= 1


# ---------------------------------------------------------------------------
# _handle_class_def: CLASS nodes, DEFINES, INHERITS
# ---------------------------------------------------------------------------


class TestClassDefinitions:
    """Class nodes, DEFINES hierarchy, nested classes."""

    def test_class_node_created(self):
        code = "class Animal:\n    pass\n"
        nodes, _ = extract_graph_from_file("test.py", code)
        names = _node_names(nodes, NodeKind.CLASS)
        assert "Animal" in names

    def test_nested_class_qualified_name(self):
        code = "class Outer:\n    class Inner:\n        def inner_method(self):\n            pass\n"
        nodes, _ = extract_graph_from_file("test.py", code)
        qualified = _qualified_names(nodes, NodeKind.CLASS)
        assert "Outer.Inner" in qualified

    def test_nested_class_method_qualified_name(self):
        code = "class Outer:\n    class Inner:\n        def inner_method(self):\n            pass\n"
        nodes, _ = extract_graph_from_file("test.py", code)
        qualified = _qualified_names(nodes, NodeKind.FUNCTION)
        assert "Outer.Inner.inner_method" in qualified

    def test_defines_hierarchical_outer_defines_inner(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        outer_defines = [
            e
            for e in edges
            if e.kind == EdgeKind.DEFINES and f"{pg}::Outer" in e.source
        ]
        targets = {e.target for e in outer_defines}
        assert any("Outer.Inner" in t for t in targets)

    def test_defines_hierarchical_inner_defines_method(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        inner_defines = [
            e
            for e in edges
            if e.kind == EdgeKind.DEFINES and f"{pg}::Outer.Inner" in e.source
        ]
        targets = {e.target for e in inner_defines}
        assert any("inner_method" in t for t in targets)


# ---------------------------------------------------------------------------
# _get_base_classes_from_arg_list, _resolve_base_class: INHERITS
# ---------------------------------------------------------------------------


class TestInheritanceEdges:
    """INHERITS edges: local and imported base classes."""

    def test_local_base_class_resolved(self):
        code = "class Animal:\n    pass\nclass Dog(Animal):\n    pass\n"
        _, edges = extract_graph_from_file("test.py", code)
        inherits = _edges_of(edges, EdgeKind.INHERITS)
        dog_inherits = [e for e in inherits if "Dog" in e.source]
        targets = {e.target for e in dog_inherits}
        assert any("Animal" in t for t in targets)

    def test_imported_base_class_resolved(self):
        code = "from abc import ABC\nclass GuideDog(ABC):\n    pass\n"
        _, edges = extract_graph_from_file("test.py", code)
        inherits = _edges_of(edges, EdgeKind.INHERITS)
        guide_inherits = [e for e in inherits if "GuideDog" in e.source]
        targets = {e.target for e in guide_inherits}
        assert any("abc::ABC" in t for t in targets)

    def test_multiple_inheritance_creates_multiple_edges(self):
        code = "class A:\n    pass\nclass B:\n    pass\nclass C(A, B):\n    pass\n"
        _, edges = extract_graph_from_file("test.py", code)
        inherits = _edges_of(edges, EdgeKind.INHERITS)
        c_inherits = [e for e in inherits if "C" in e.source]
        assert len(c_inherits) == 2

    def test_dotted_base_class_resolved(self):
        code = "from abc import ABC\nclass X(ABC):\n    pass\n"
        _, edges = extract_graph_from_file("test.py", code)
        inherits = _edges_of(edges, EdgeKind.INHERITS)
        assert any("abc::ABC" in e.target for e in inherits)


# ---------------------------------------------------------------------------
# _is_property: @property detection for self.repo.save() resolution
# ---------------------------------------------------------------------------


class TestPropertyDetection:
    """@property methods register class attribute for call resolution."""

    def test_property_return_type_registered(self):
        """@property def repo() -> Repo enables self.repo.save() resolution."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        # ServiceWithLazyRepo.do_work calls self.repo.save() -> RepositoryPort.save
        lazy_calls = [e for e in calls if "ServiceWithLazyRepo.do_work" in e.source]
        targets = {e.target for e in lazy_calls}
        assert any("RepositoryPort.save" in t for t in targets)


# ---------------------------------------------------------------------------
# Typed parameters: param injection registration
# ---------------------------------------------------------------------------


class TestTypedParameterRegistration:
    """_handle_function_def: typed params register for param injection."""

    def test_param_type_registers_instance(self):
        """def f(processor: DataProcessor): processor.process() resolves."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        proc_calls = [
            e for e in calls if "process_with_injected_dependency" in e.source
        ]
        targets = {e.target for e in proc_calls}
        assert any("DataProcessor.process" in t for t in targets)
