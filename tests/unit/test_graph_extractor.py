"""Tests for indexer.graph.extractor."""

from indexer.core.models import EdgeKind, NodeKind
from indexer.graph.extractor import GraphExtractor, _extract_callee_name

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

    def test_builtin_calls_filtered(self):
        code = (
            "def process():\n"
            "    items = []\n"
            "    items.append(1)\n"
            "    x = len(items)\n"
            "    d = dict()\n"
            "    print(x)\n"
            "    custom_func()\n"
        )
        nodes, edges = self.extractor.extract_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "custom_func" in targets
        assert "append" not in targets
        assert "len" not in targets
        assert "dict" not in targets
        assert "print" not in targets
