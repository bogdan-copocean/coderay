"""Tests for indexer.graph.extractor."""

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.extractor import (
    GraphExtractor,
    _extract_callee_name,
    _resolve_relative_import,
    build_callee_filter,
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


class TestExtractCalleeName:
    def test_simple_name(self):
        assert _extract_callee_name("foo") == "foo"

    def test_strips_self(self):
        assert _extract_callee_name("self.bark") == "bark"

    def test_strips_self_chain(self):
        assert _extract_callee_name("self._store.delete_by_paths") == "delete_by_paths"

    def test_strips_this(self):
        assert _extract_callee_name("this.render") == "render"

    def test_dotted_chain(self):
        assert _extract_callee_name("a.b.c") == "c"

    def test_single_method(self):
        assert _extract_callee_name("obj.method") == "method"


class TestGraphExtractor:
    def setup_method(self):
        self.extractor = GraphExtractor()

    def test_extracts_module_node(self):
        nodes, edges = self.extractor.extract_from_file("test.py", "x = 1")
        module_nodes = [n for n in nodes if n.kind == NodeKind.MODULE]
        assert len(module_nodes) == 1
        assert module_nodes[0].id == "test.py"

    def test_extracts_imports(self):
        nodes, edges = self.extractor.extract_from_file("test.py", SAMPLE)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        targets = {e.target for e in import_edges}
        assert "os" in targets
        assert "pathlib" in targets

    def test_extracts_class_and_function_nodes(self):
        nodes, edges = self.extractor.extract_from_file("test.py", SAMPLE)
        names = {n.name for n in nodes}
        assert "Animal" in names
        assert "Dog" in names
        assert "helper" in names
        assert "speak" in names
        assert "bark" in names

    def test_extracts_defines_edges(self):
        nodes, edges = self.extractor.extract_from_file("test.py", SAMPLE)
        defines = [e for e in edges if e.kind == EdgeKind.DEFINES]
        targets = {e.target for e in defines}
        assert any("Animal" in t for t in targets)
        assert any("helper" in t for t in targets)

    def test_extracts_inherits_edges(self):
        nodes, edges = self.extractor.extract_from_file("test.py", SAMPLE)
        inherits = [e for e in edges if e.kind == EdgeKind.INHERITS]
        assert len(inherits) >= 1
        assert any("Animal" in e.target for e in inherits)

    def test_extracts_calls_edges_with_stripped_self(self):
        nodes, edges = self.extractor.extract_from_file("test.py", SAMPLE)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        callee_names = {e.target for e in calls}
        assert "bark" in callee_names

    def test_call_targets_are_short_names(self):
        code = "class Foo:\n    def run(self):\n        self.helper()\n        self._store.save()\n"
        nodes, edges = self.extractor.extract_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "helper" in targets
        assert "save" in targets
        assert "self.helper" not in targets

    def test_empty_file(self):
        nodes, edges = self.extractor.extract_from_file("empty.py", "")
        assert len(nodes) == 1
        assert len(edges) == 0

    def test_qualified_names(self):
        nodes, edges = self.extractor.extract_from_file("test.py", SAMPLE)
        dog_speak = [
            n for n in nodes if n.name == "speak" and "Dog" in n.qualified_name
        ]
        assert len(dog_speak) >= 1

    def test_module_level_calls_captured(self):
        code = "from flask import Flask\napp = Flask(__name__)\n"
        nodes, edges = self.extractor.extract_from_file("app.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        assert len(calls) >= 1
        assert calls[0].source == "app.py"
        assert calls[0].target == "Flask"

    def test_relative_import_resolved(self):
        code = "from ..common.base_repo import BaseRepo\n"
        nodes, edges = self.extractor.extract_from_file("src/a/b/c/file.py", code)
        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) == 1
        assert import_edges[0].target == "src/a/b/common/base_repo"

    def test_di_style_call_creates_edge(self):
        """self.injected_service.method() should produce a CALLS edge to 'method'."""
        code = (
            "class Handler:\n"
            "    def handle(self):\n"
            "        result = self.survey_service.get_count_by_survey_id(sid)\n"
            "        return result\n"
        )
        nodes, edges = self.extractor.extract_from_file("api/views.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "get_count_by_survey_id" in targets, (
            f"DI-style call not captured. Got: {targets}"
        )

    def test_chained_attribute_call_creates_edge(self):
        """obj.a.b.c() should produce a CALLS edge to 'c'."""
        code = "def process():\n    result = app.services.registry.find_handler(name)\n"
        nodes, edges = self.extractor.extract_from_file("test.py", code)
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
        nodes, edges = self.extractor.extract_from_file("test.py", code)
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
        nodes, edges = self.extractor.extract_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "append" in targets
        assert "forEach" in targets
        assert "custom_func" in targets


class TestBuildCalleeFilter:
    """Tests for the configurable callee filter."""

    def test_default_excludes_python_builtins(self):
        filt = build_callee_filter()
        assert "len" in filt
        assert "print" in filt
        assert "isinstance" in filt
        assert "int" in filt

    def test_non_builtins_not_excluded_by_default(self):
        """Common methods like append/forEach are NOT in the default filter."""
        filt = build_callee_filter()
        assert "append" not in filt
        assert "forEach" not in filt
        assert "Println" not in filt

    def test_exclude_callees_adds_names(self):
        from types import SimpleNamespace

        from coderay.core.config import _reset_config_for_testing

        _reset_config_for_testing(
            SimpleNamespace(graph={"exclude_callees": ["our_sdk_helper", "append"]})
        )
        try:
            filt = build_callee_filter()
        finally:
            _reset_config_for_testing(None)
        assert "our_sdk_helper" in filt
        assert "append" in filt
        assert "len" in filt  # builtins still present

    def test_include_callees_overrides_default(self):
        from types import SimpleNamespace

        from coderay.core.config import _reset_config_for_testing

        _reset_config_for_testing(
            SimpleNamespace(graph={"include_callees": ["isinstance", "print"]})
        )
        try:
            filt = build_callee_filter()
        finally:
            _reset_config_for_testing(None)
        assert "isinstance" not in filt
        assert "print" not in filt
        assert "len" in filt  # other builtins still present

    def test_both_exclude_and_include(self):
        from types import SimpleNamespace

        from coderay.core.config import _reset_config_for_testing

        _reset_config_for_testing(
            SimpleNamespace(
                graph={
                    "exclude_callees": ["my_helper"],
                    "include_callees": ["isinstance"],
                }
            )
        )
        try:
            filt = build_callee_filter()
        finally:
            _reset_config_for_testing(None)
        assert "my_helper" in filt
        assert "isinstance" not in filt

    def test_none_config_uses_defaults(self):
        filt = build_callee_filter()
        assert "len" in filt

    def test_empty_config_uses_defaults(self):
        filt = build_callee_filter()
        assert "len" in filt


class TestConfigurableExtraction:
    """Test that GraphExtractor respects config (via get_config()) end-to-end."""

    def test_include_callees_creates_edge_for_builtin(self):
        """When 'isinstance' is included via config, it should appear as a CALLS edge."""
        from types import SimpleNamespace

        from coderay.core.config import _reset_config_for_testing

        _reset_config_for_testing(
            SimpleNamespace(graph={"include_callees": ["isinstance"]})
        )
        try:
            ext = GraphExtractor()
            code = "def check(x):\n    isinstance(x, str)\n"
            _, edges = ext.extract_from_file("test.py", code)
            calls = [e for e in edges if e.kind == EdgeKind.CALLS]
            targets = {e.target for e in calls}
            assert "isinstance" in targets
        finally:
            _reset_config_for_testing(None)

    def test_exclude_callees_filters_custom_name(self):
        """A user-excluded name should not appear as a CALLS edge."""
        from types import SimpleNamespace

        from coderay.core.config import _reset_config_for_testing

        _reset_config_for_testing(
            SimpleNamespace(graph={"exclude_callees": ["my_custom_func"]})
        )
        try:
            ext = GraphExtractor()
            code = "def run():\n    my_custom_func()\n    other_func()\n"
            _, edges = ext.extract_from_file("test.py", code)
            calls = [e for e in edges if e.kind == EdgeKind.CALLS]
            targets = {e.target for e in calls}
            assert "my_custom_func" not in targets
            assert "other_func" in targets
        finally:
            _reset_config_for_testing(None)

    def test_default_extractor_filters_builtins(self, default_config):
        """Default GraphExtractor (no config) still filters builtins."""
        ext = GraphExtractor()
        code = "def f():\n    len([])\n    custom()\n"
        _, edges = ext.extract_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "len" not in targets
        assert "custom" in targets
