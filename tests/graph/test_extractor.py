"""Tests for graph.extractor."""

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.extractor import (
    _PYTHON_BUILTINS,
    FileContext,
    GraphTreeSitterParser,
    _resolve_relative_import,
    build_module_filter,
    extract_graph_from_file,
)

SAMPLE = """\
import os
from pathlib import Path

class Animal:
    def speak(self):
        return "..."

class Dog(Animal):
    def speak(self):
        return self.bark()

    def bark(self):
        return "Woof"

def helper():
    d = Dog()
    d.speak()
"""


class TestResolveRelativeImport:
    def test_single_dot(self):
        result = _resolve_relative_import("src/a/b/file.py", ".foo")
        assert result == "src/a/b/foo"

    def test_double_dot(self):
        result = _resolve_relative_import("src/a/b/c/file.py", "..foo.bar")
        assert result == "src/a/b/foo/bar"

    def test_triple_dot(self):
        result = _resolve_relative_import("src/a/b/c/file.py", "...foo")
        assert result == "src/a/foo"

    def test_dot_only(self):
        result = _resolve_relative_import("src/a/b/file.py", ".")
        assert result == "src/a/b"

    def test_too_many_dots_returns_none(self):
        result = _resolve_relative_import("file.py", "...foo")
        assert result is None


class TestFileContext:
    """Unit tests for the FileContext name-resolution data structure."""

    def test_register_and_resolve_import(self):
        ctx = FileContext()
        ctx.register_import("Flask", "flask::Flask")
        assert ctx.resolve("Flask") == "flask::Flask"

    def test_register_and_resolve_definition(self):
        ctx = FileContext()
        ctx.register_definition("MyClass", "file.py::MyClass", is_class=True)
        assert ctx.resolve("MyClass") == "file.py::MyClass"
        assert ctx.is_class("MyClass")

    def test_function_definition_not_class(self):
        ctx = FileContext()
        ctx.register_definition("helper", "file.py::helper")
        assert ctx.resolve("helper") == "file.py::helper"
        assert not ctx.is_class("helper")

    def test_register_instance_and_method_call(self):
        ctx = FileContext()
        ctx.register_instance("app", "flask::Flask")
        assert ctx.resolve_instance("app") == "flask::Flask"
        assert ctx.resolve_method_call("app", "run") == "flask::Flask.run"

    def test_register_alias(self):
        ctx = FileContext()
        ctx.register_import("func", "module::func")
        ctx.register_alias("my_func", "module::func")
        assert ctx.resolve("my_func") == "module::func"

    def test_last_write_wins(self):
        ctx = FileContext()
        ctx.register_import("name", "a::name")
        ctx.register_import("name", "b::name")
        assert ctx.resolve("name") == "b::name"

    def test_resolve_unknown_returns_none(self):
        ctx = FileContext()
        assert ctx.resolve("unknown") is None
        assert ctx.resolve_instance("unknown") is None
        assert ctx.resolve_method_call("unknown", "method") is None


class TestGraphExtraction:
    def test_extracts_module_node(self):
        nodes, edges = extract_graph_from_file("test.py", "x = 1")
        module_nodes = [n for n in nodes if n.kind == NodeKind.MODULE]
        assert len(module_nodes) == 1
        assert module_nodes[0].id == "test.py"

    def test_extracts_imports(self):
        nodes, edges = extract_graph_from_file("test.py", SAMPLE)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        targets = {e.target for e in import_edges}
        assert "os" in targets
        assert "pathlib::Path" in targets

    def test_extracts_class_and_function_nodes(self):
        nodes, edges = extract_graph_from_file("test.py", SAMPLE)
        names = {n.name for n in nodes}
        assert "Animal" in names
        assert "Dog" in names
        assert "helper" in names
        assert "speak" in names
        assert "bark" in names

    def test_extracts_defines_edges(self):
        nodes, edges = extract_graph_from_file("test.py", SAMPLE)
        defines = [e for e in edges if e.kind == EdgeKind.DEFINES]
        targets = {e.target for e in defines}
        assert any("Animal" in t for t in targets)
        assert any("helper" in t for t in targets)

    def test_extracts_inherits_edges(self):
        nodes, edges = extract_graph_from_file("test.py", SAMPLE)
        inherits = [e for e in edges if e.kind == EdgeKind.INHERITS]
        assert len(inherits) >= 1
        assert any("Animal" in e.target for e in inherits)

    def test_self_call_resolves_to_class_method(self):
        """self.bark() inside Dog.speak resolves to test.py::Dog.bark."""
        nodes, edges = extract_graph_from_file("test.py", SAMPLE)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "test.py::Dog.bark" in targets

    def test_self_simple_method_resolves(self):
        """self.helper() inside Foo.run resolves to test.py::Foo.helper."""
        code = (
            "class Foo:\n"
            "    def run(self):\n"
            "        self.helper()\n"
            "        self._store.save()\n"
        )
        nodes, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "test.py::Foo.helper" in targets
        assert "save" in targets
        assert "self.helper" not in targets

    def test_empty_file(self):
        nodes, edges = extract_graph_from_file("empty.py", "")
        assert len(nodes) == 1
        assert len(edges) == 0

    def test_qualified_names(self):
        nodes, edges = extract_graph_from_file("test.py", SAMPLE)
        dog_speak = [
            n for n in nodes if n.name == "speak" and "Dog" in n.qualified_name
        ]
        assert len(dog_speak) >= 1

    def test_module_level_calls_captured(self):
        """Imported Flask resolves to flask::Flask when called."""
        code = "from flask import Flask\napp = Flask(__name__)\n"
        nodes, edges = extract_graph_from_file("app.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        assert len(calls) >= 1
        assert calls[0].source == "app.py"
        assert calls[0].target == "flask::Flask"

    def test_relative_import_resolved(self):
        code = "from ..common.base_repo import BaseRepo\n"
        nodes, edges = extract_graph_from_file("src/a/b/c/file.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) == 1
        assert import_edges[0].target == "src/a/b/common/base_repo::BaseRepo"

    def test_di_style_call_creates_edge(self):
        """self.injected_service.method() should produce a CALLS edge to 'method'."""
        code = (
            "class Handler:\n"
            "    def handle(self):\n"
            "        result = self.user_service.get_count_by_user_id(uid)\n"
            "        return result\n"
        )
        nodes, edges = extract_graph_from_file("api/views.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "get_count_by_user_id" in targets, (
            f"DI-style call not captured. Got: {targets}"
        )

    def test_chained_attribute_call_creates_edge(self):
        """obj.a.b.c() should produce a CALLS edge to 'c'."""
        code = "def process():\n    result = app.services.registry.find_handler(name)\n"
        nodes, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "find_handler" in targets

    def test_python_builtin_calls_filtered(self):
        """Python builtins are excluded by default."""
        code = (
            "def process():\n"
            "    x = len([])\n"
            "    d = dict()\n"
            "    print(x)\n"
            "    custom_func()\n"
        )
        nodes, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "custom_func" in targets
        assert "len" not in targets
        assert "dict" not in targets
        assert "print" not in targets

    def test_non_builtin_method_calls_kept(self):
        """Methods not in dir(builtins) are kept as CALLS edges."""
        code = (
            "def process():\n"
            "    items = []\n"
            "    items.append(1)\n"
            "    data.forEach(fn)\n"
            "    custom_func()\n"
        )
        nodes, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "append" in targets
        assert "forEach" in targets
        assert "custom_func" in targets

    # ------------------------------------------------------------------
    # New resolution tests
    # ------------------------------------------------------------------

    def test_bare_import_creates_edge(self):
        """``import os`` should produce an IMPORTS edge with target 'os'."""
        code = "import os\nimport sys\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        targets = {e.target for e in import_edges}
        assert "os" in targets
        assert "sys" in targets

    def test_aliased_import_resolution(self):
        """``import math as m`` then ``m.sqrt()`` resolves via alias."""
        code = "import math as m\nm.sqrt(4)\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert any(e.target == "math" for e in import_edges)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "math.sqrt" in targets

    def test_aliased_from_import_resolution(self):
        """``from collections import defaultdict as dd`` then ``dd()``."""
        code = "from collections import defaultdict as dd\ndd(int)\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert any(e.target == "collections::defaultdict" for e in import_edges)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "collections::defaultdict" in targets

    def test_function_defined_and_called_locally(self):
        """A function defined and called in the same file resolves to full path."""
        code = "def my_helper():\n    pass\n\nmy_helper()\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "test.py::my_helper" in targets

    def test_instance_method_call_resolved(self):
        """``obj = MyClass()`` then ``obj.method()`` resolves to MyClass.method."""
        code = (
            "class MyClass:\n"
            "    def method(self):\n"
            "        pass\n"
            "\n"
            "obj = MyClass()\n"
            "obj.method()\n"
        )
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "test.py::MyClass.method" in targets

    def test_imported_instance_method_resolved(self):
        """Instance of an imported class resolves method calls."""
        code = "from flask import Flask\napp = Flask(__name__)\napp.run()\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "flask::Flask.run" in targets

    def test_alias_assignment_resolved(self):
        """``my_func = imported_func`` then ``my_func()`` resolves to original."""
        code = "from module import func\nmy_func = func\nmy_func()\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "module::func" in targets

    def test_self_method_resolves_to_enclosing_class(self):
        """self.method() resolves to EnclosingClass.method."""
        code = (
            "class Dog:\n"
            "    def speak(self):\n"
            "        return self.bark()\n"
            "    def bark(self):\n"
            "        return 'Woof'\n"
        )
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "test.py::Dog.bark" in targets

    def test_multiple_bare_imports(self):
        """``import os, sys`` creates IMPORTS edges for both."""
        code = "import os, sys\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        targets = {e.target for e in import_edges}
        assert "os" in targets
        assert "sys" in targets


class TestBuildModuleFilter:
    """Tests for the configurable module filter."""

    def test_default_excludes_core_modules(self):
        filt = build_module_filter()
        assert "builtins" in filt
        assert "typing" in filt
        assert "abc" in filt

    def test_project_modules_not_excluded(self):
        """Common project dependencies are NOT in the default filter."""
        filt = build_module_filter()
        assert "flask" not in filt
        assert "myproject" not in filt

    def test_exclude_modules_adds_entries(self):
        from coderay.core.config import Config, GraphConfig, _reset_config_for_testing

        _reset_config_for_testing(
            Config(graph=GraphConfig(exclude_modules=["numpy", "pandas"]))
        )
        try:
            filt = build_module_filter()
        finally:
            _reset_config_for_testing(None)
        assert "numpy" in filt
        assert "pandas" in filt
        assert "builtins" in filt

    def test_include_modules_overrides_default(self):
        from coderay.core.config import Config, GraphConfig, _reset_config_for_testing

        _reset_config_for_testing(
            Config(graph=GraphConfig(include_modules=["typing"]))
        )
        try:
            filt = build_module_filter()
        finally:
            _reset_config_for_testing(None)
        assert "typing" not in filt
        assert "builtins" in filt

    def test_both_exclude_and_include(self):
        from coderay.core.config import Config, GraphConfig, _reset_config_for_testing

        _reset_config_for_testing(
            Config(
                graph=GraphConfig(
                    exclude_modules=["requests"],
                    include_modules=["typing"],
                )
            )
        )
        try:
            filt = build_module_filter()
        finally:
            _reset_config_for_testing(None)
        assert "requests" in filt
        assert "typing" not in filt

    def test_none_config_uses_defaults(self):
        filt = build_module_filter()
        assert "builtins" in filt

    def test_python_builtins_constant(self):
        """Verify the _PYTHON_BUILTINS set contains expected names."""
        assert "print" in _PYTHON_BUILTINS
        assert "len" in _PYTHON_BUILTINS
        assert "isinstance" in _PYTHON_BUILTINS


class TestConfigurableExtraction:
    """Test that extraction respects module-based filtering end-to-end."""

    def test_default_extraction_filters_builtins(self, default_config):
        """Unresolved bare builtins (print, len) are filtered by default."""
        code = "def f():\n    len([])\n    custom()\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "len" not in targets
        assert "custom" in targets

    def test_excluded_module_filters_resolved_call(self):
        """Calls resolved to an excluded module are filtered."""
        code = "from typing import cast\ncast(str, x)\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "typing::cast" not in targets

    def test_project_defined_shadowing_builtin_not_filtered(self):
        """A locally defined function named 'print' should NOT be filtered."""
        code = "def print(msg):\n    pass\n\ndef run():\n    print('hello')\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert any("print" in t for t in targets)

    def test_excluded_module_filters_import_edge(self):
        """Imports from excluded modules should not produce IMPORTS edges."""
        code = "from typing import Optional\nfrom flask import Flask\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_targets = {e.target for e in edges if e.kind == EdgeKind.IMPORTS}
        assert "typing::Optional" not in import_targets
        assert "flask::Flask" in import_targets

    def test_excluded_module_import_still_resolves(self):
        """Excluded imports are filtered from edges but still resolve in calls."""
        code = "from typing import cast\n\ndef f():\n    cast(str, x)\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_targets = {e.target for e in edges if e.kind == EdgeKind.IMPORTS}
        assert "typing::cast" not in import_targets
        call_targets = {e.target for e in edges if e.kind == EdgeKind.CALLS}
        assert "typing::cast" not in call_targets
