"""Tests for CallHandlerMixin: CALLS edges, resolution, filtering.

Covers: simple name, self.method, self.attr.method, super(), chains,
builtins/excluded filtering, instance tracking, decorators, __call__, partial.
"""

from pathlib import Path

from coderay.core.models import EdgeKind
from coderay.graph.extractor import extract_graph_from_file

SAMPLE_PATH = Path(__file__).parent.parent / "graph_sample.py"


def _calls_from(edges, source_fragment: str) -> set[str]:
    return {
        e.target
        for e in edges
        if e.kind == EdgeKind.CALLS and source_fragment in e.source
    }


def _call_targets(edges) -> set[str]:
    return {e.target for e in edges if e.kind == EdgeKind.CALLS}


# ---------------------------------------------------------------------------
# _resolve_simple_name_targets: func(), obj() via import/alias/definition
# ---------------------------------------------------------------------------


class TestSimpleNameResolution:
    """Calls to simple names: imports, aliases, definitions."""

    def test_imported_function_call_resolved(self):
        code = "from flask import Flask\napp = Flask(__name__)\n"
        _, edges = extract_graph_from_file("app.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        assert len(calls) >= 1
        assert calls[0].target == "flask::Flask"

    def test_locally_defined_function_call_resolved(self):
        code = "def my_helper():\n    pass\n\nmy_helper()\n"
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "test.py::my_helper" in targets

    def test_aliased_import_call_resolved(self):
        code = "import math as m\nm.sqrt(4)\n"
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "math.sqrt" in targets

    def test_aliased_from_import_call_resolved(self):
        code = "from collections import defaultdict as dd\ndd(int)\n"
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "collections::defaultdict" in targets

    def test_alias_assignment_call_resolved(self):
        code = "from module import func\nmy_func = func\nmy_func()\n"
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "module::func" in targets


# ---------------------------------------------------------------------------
# _resolve_self_targets: self.method(), self.attr.method()
# ---------------------------------------------------------------------------


class TestSelfMethodResolution:
    """self.method() and self.attr.method() resolution."""

    def test_self_method_resolves_to_enclosing_class(self):
        code = (
            "class Dog:\n"
            "    def speak(self):\n"
            "        return self.bark()\n"
            "    def bark(self):\n"
            "        return 'Woof'\n"
        )
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "test.py::Dog.bark" in targets

    def test_self_private_method_resolves(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "Animal.move")
        assert f"{pg}::Animal._walk" in targets

    def test_self_bootstrap_calls_resolve(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "Service.bootstrap")
        assert f"{pg}::Service._setup_logging" in targets
        assert f"{pg}::Service._connect" in targets

    def test_composition_via_self_attribute(self):
        """self.client = HttpClient(); self.client.get() — HttpClient.get."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "Service.fetch")
        assert f"{pg}::HttpClient.get" in targets

    def test_nested_class_instantiation_via_self(self):
        """self.Inner() in Outer.use_inner resolves to Outer.Inner."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "Outer.use_inner")
        assert any("Outer.Inner" in t for t in targets)


# ---------------------------------------------------------------------------
# _resolve_super_targets: super().method()
# ---------------------------------------------------------------------------


class TestSuperCallResolution:
    """super().method() resolves to parent class method."""

    def test_super_call_resolved(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "ChildWithSuper.run")
        assert f"{pg}::ParentWithRun.run" in targets


# ---------------------------------------------------------------------------
# _resolve_chain_targets: obj.method(), obj.a.b.c()
# ---------------------------------------------------------------------------


class TestChainResolution:
    """Chained attribute calls: obj.attr.method()."""

    def test_simple_chain_resolved(self):
        code = "def process():\n    result = app.services.registry.find_handler(name)\n"
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "find_handler" in targets

    def test_di_style_call_creates_edge(self):
        code = (
            "class Handler:\n"
            "    def handle(self):\n"
            "        result = self.user_service.get_count_by_user_id(uid)\n"
        )
        _, edges = extract_graph_from_file("api/views.py", code)
        targets = _call_targets(edges)
        assert "get_count_by_user_id" in targets

    def test_deep_chained_access_resolved(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "chained_access_example")
        assert f"{pg}::HttpClient.get" in targets


# ---------------------------------------------------------------------------
# _is_excluded: builtins and excluded modules filtered
# ---------------------------------------------------------------------------


class TestCallFiltering:
    """Builtins and excluded modules filtered from CALLS edges."""

    def test_builtins_filtered(self):
        code = (
            "def process():\n"
            "    x = len([])\n"
            "    d = dict()\n"
            "    print(x)\n"
            "    custom_func()\n"
        )
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "custom_func" in targets
        assert "len" not in targets
        assert "dict" not in targets
        assert "print" not in targets

    def test_non_builtin_method_calls_kept(self):
        code = (
            "def process():\n"
            "    items = []\n"
            "    items.append(1)\n"
            "    data.forEach(fn)\n"
            "    custom_func()\n"
        )
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "append" in targets
        assert "forEach" in targets
        assert "custom_func" in targets

    def test_project_defined_shadowing_builtin_not_filtered(self):
        code = "def print(msg):\n    pass\n\ndef run():\n    print('hello')\n"
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert any("print" in t for t in targets)

    def test_excluded_module_call_filtered(self):
        code = "from typing import cast\ncast(str, x)\n"
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "typing::cast" not in targets


# ---------------------------------------------------------------------------
# _maybe_track_instantiation: x = SomeClass()
# ---------------------------------------------------------------------------


class TestInstanceTracking:
    """Instantiation tracking for method call resolution."""

    def test_instance_method_call_resolved(self):
        code = (
            "class MyClass:\n"
            "    def method(self):\n"
            "        pass\n"
            "\n"
            "obj = MyClass()\n"
            "obj.method()\n"
        )
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "test.py::MyClass.method" in targets

    def test_imported_instance_method_resolved(self):
        code = "from flask import Flask\napp = Flask(__name__)\napp.run()\n"
        _, edges = extract_graph_from_file("test.py", code)
        targets = _call_targets(edges)
        assert "flask::Flask.run" in targets

    def test_factory_pattern_resolved(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_factory_client")
        assert f"{pg}::HttpClient.get" in targets


# ---------------------------------------------------------------------------
# _handle_decorator: @my_decorator
# ---------------------------------------------------------------------------


class TestDecoratorCalls:
    """Decorator application creates CALLS edges."""

    def test_decorator_call_emitted(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        decorator_calls = [
            e for e in edges if e.kind == EdgeKind.CALLS and "my_decorator" in e.target
        ]
        assert len(decorator_calls) >= 2

    def test_static_method_call_at_module_level(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        module_calls = _calls_from(edges, pg)
        assert f"{pg}::Config.from_env" in module_calls


# ---------------------------------------------------------------------------
# __call__ protocol, functools.partial
# ---------------------------------------------------------------------------


class TestCallProtocolAndPartial:
    """__call__ and partial resolution."""

    def test_call_protocol_resolved(self):
        """h = CallableHandler(); h('test') — CallableHandler.__call__."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_callable_handler")
        assert f"{pg}::CallableHandler.__call__" in targets

    def test_partial_resolved(self):
        """hello = partial(greeter, 'Hello'); hello('World') — greeter."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_partial")
        assert f"{pg}::greeter" in targets
