"""Test graph.extractor: FileContext, build_module_filter, integration."""

from pathlib import Path

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.extractor import (
    FileContext,
    build_module_filter,
    extract_graph_from_file,
)


class TestFileContext:
    """Test FileContext name-resolution."""

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
    """Minimal integration for extract_graph_from_file."""

    def test_extracts_module_node(self):
        nodes, edges = extract_graph_from_file("test.py", "x = 1")
        module_nodes = [n for n in nodes if n.kind == NodeKind.MODULE]
        assert len(module_nodes) == 1
        assert module_nodes[0].id == "test.py"

    def test_empty_file(self):
        nodes, edges = extract_graph_from_file("empty.py", "")
        assert len(nodes) == 1
        assert len(edges) == 0

    def test_simple_extraction_produces_nodes_and_edges(self):
        code = "import os\nclass Foo:\n    def bar(self):\n        pass\n"
        nodes, edges = extract_graph_from_file("test.py", code)
        assert len(nodes) >= 3  # module, class, method
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) >= 1


class TestBuildModuleFilter:
    """Test configurable module filter."""

    def test_default_excludes_core_modules(self):
        filt = build_module_filter()
        assert "builtins" in filt
        assert "typing" in filt
        assert "abc" in filt

    def test_project_modules_not_excluded(self):
        filt = build_module_filter()
        assert "flask" not in filt
        assert "myproject" not in filt

    def test_exclude_modules_adds_entries(self):
        from coderay.core.config import _reset_config_for_testing, config_for_repo

        _reset_config_for_testing(
            config_for_repo(
                Path.cwd(),
                {"graph": {"exclude_modules": ["numpy", "pandas"]}},
            )
        )
        try:
            filt = build_module_filter()
        finally:
            _reset_config_for_testing(None)
        assert "numpy" in filt
        assert "pandas" in filt
        assert "builtins" in filt

    def test_include_modules_overrides_default(self):
        from coderay.core.config import _reset_config_for_testing, config_for_repo

        _reset_config_for_testing(
            config_for_repo(Path.cwd(), {"graph": {"include_modules": ["typing"]}})
        )
        try:
            filt = build_module_filter()
        finally:
            _reset_config_for_testing(None)
        assert "typing" not in filt
        assert "builtins" in filt

    def test_both_exclude_and_include(self):
        from coderay.core.config import _reset_config_for_testing, config_for_repo

        _reset_config_for_testing(
            config_for_repo(
                Path.cwd(),
                {
                    "graph": {
                        "exclude_modules": ["requests"],
                        "include_modules": ["typing"],
                    }
                },
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


class TestConfigurableExtraction:
    """Test extraction respects module-based filtering."""

    def test_default_extraction_filters_builtins(self, default_config):
        code = "def f():\n    len([])\n    custom()\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "len" not in targets
        assert "custom" in targets

    def test_excluded_module_filters_resolved_call(self):
        code = "from typing import cast\ncast(str, x)\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "typing::cast" not in targets

    def test_project_defined_shadowing_builtin_not_filtered(self):
        code = "def print(msg):\n    pass\n\ndef run():\n    print('hello')\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert any("print" in t for t in targets)

    def test_excluded_module_filters_import_edge(self):
        code = "from typing import Optional\nfrom flask import Flask\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_targets = {e.target for e in edges if e.kind == EdgeKind.IMPORTS}
        assert "typing::Optional" not in import_targets
        assert "flask::Flask" in import_targets

    def test_excluded_module_import_still_resolves(self):
        code = "from typing import cast\n\ndef f():\n    cast(str, x)\n"
        _, edges = extract_graph_from_file("test.py", code)
        import_targets = {e.target for e in edges if e.kind == EdgeKind.IMPORTS}
        assert "typing::cast" not in import_targets
        call_targets = {e.target for e in edges if e.kind == EdgeKind.CALLS}
        assert "typing::cast" not in call_targets
