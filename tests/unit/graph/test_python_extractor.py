"""Focused unit tests for Python graph extraction (input/output per handler)."""

from __future__ import annotations

from coderay.core.models import NodeKind
from coderay.graph.extractors.python.extractor import PythonGraphExtractor
from coderay.graph.facts import (
    CallsEdge,
    ImportsEdge,
    InheritsEdge,
    SymbolDefinition,
)
from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.base import get_parse_context

FILE = "test.py"


def _extract(
    source: str,
    *,
    module_index: dict[str, str] | None = None,
) -> tuple[list, FileNameBindings]:
    """Build extractor from source snippet and return (facts, file_ctx)."""
    ctx = get_parse_context(FILE, source)
    ext = PythonGraphExtractor(ctx, module_index=module_index)
    facts = ext.extract_facts_list()
    return facts, ext._file_ctx


def _definitions(facts) -> list[SymbolDefinition]:
    return sorted(
        [f for f in facts if isinstance(f, SymbolDefinition)],
        key=lambda d: d.start_line,
    )


def _calls(facts) -> set[tuple[str, str]]:
    return {(f.source_id, f.target) for f in facts if isinstance(f, CallsEdge)}


def _imports(facts) -> set[tuple[str, str]]:
    return {(f.source_id, f.target) for f in facts if isinstance(f, ImportsEdge)}


def _inherits(facts) -> set[tuple[str, str]]:
    return {(f.source_id, f.target) for f in facts if isinstance(f, InheritsEdge)}


# ======================================================================
# Definitions
# ======================================================================


class TestDefinitions:
    def test_function_def(self):
        facts, _ = _extract("def foo():\n    pass\n")
        defs = _definitions(facts)
        assert len(defs) == 1
        assert defs[0].name == "foo"
        assert defs[0].kind == NodeKind.FUNCTION

    def test_class_def(self):
        facts, _ = _extract("class Foo:\n    pass\n")
        defs = _definitions(facts)
        assert len(defs) == 1
        assert defs[0].name == "Foo"
        assert defs[0].kind == NodeKind.CLASS

    def test_nested_class_method(self):
        facts, _ = _extract("class Foo:\n    def bar(self):\n        pass\n")
        defs = _definitions(facts)
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"Foo", "bar"}

    def test_decorated_function(self):
        source = "def deco(f): return f\n\n@deco\ndef foo():\n    pass\n"
        facts, _ = _extract(source)
        defs = _definitions(facts)
        names = {d.name for d in defs}
        assert "foo" in names
        assert "deco" in names


# ======================================================================
# Imports
# ======================================================================


class TestImports:
    def test_from_import(self):
        facts, ctx = _extract("from os.path import join\n")
        imps = _imports(facts)
        assert len(imps) == 1
        (src, tgt) = next(iter(imps))
        assert src == FILE
        assert "join" in tgt

    def test_bare_import(self):
        facts, ctx = _extract("import os\n")
        imps = _imports(facts)
        assert len(imps) == 1
        (_, tgt) = next(iter(imps))
        assert tgt == "os"

    def test_aliased_import(self):
        facts, ctx = _extract("from os.path import join as j\n")
        resolved = ctx.resolve("j")
        assert resolved is not None
        assert "join" in resolved

    def test_relative_import(self):
        ctx = get_parse_context("pkg/mod.py", "from . import util\n")
        ext = PythonGraphExtractor(ctx)
        facts = ext.extract_facts_list()
        imps = _imports(facts)
        assert len(imps) == 1

    def test_import_registers_in_file_context(self):
        _, ctx = _extract("from mymod import MyClass\n")
        assert ctx.resolve("MyClass") is not None


# ======================================================================
# Calls
# ======================================================================


class TestCalls:
    def test_simple_call(self):
        source = "def caller():\n    foo()\n"
        facts, _ = _extract(source)
        calls = _calls(facts)
        assert any(tgt == "foo" for _, tgt in calls)

    def test_self_method_call(self):
        source = (
            "class Svc:\n"
            "    def run(self):\n"
            "        self.helper()\n"
            "    def helper(self):\n"
            "        pass\n"
        )
        facts, _ = _extract(source)
        calls = _calls(facts)
        assert any("Svc.helper" in tgt for _, tgt in calls)

    def test_super_call(self):
        source = (
            "class Base:\n"
            "    def process(self): pass\n"
            "class Child(Base):\n"
            "    def process(self):\n"
            "        super().process()\n"
        )
        facts, _ = _extract(source)
        calls = _calls(facts)
        assert any("Base.process" in tgt for _, tgt in calls)

    def test_decorator_call(self):
        source = "def deco(f): return f\n\n@deco\ndef foo():\n    pass\n"
        facts, _ = _extract(source)
        calls = _calls(facts)
        assert any("deco" in tgt for _, tgt in calls)

    def test_chained_call(self):
        source = (
            "from svc import Service\ndef run():\n    s = Service()\n    s.process()\n"
        )
        facts, _ = _extract(source)
        calls = _calls(facts)
        assert any("process" in tgt for _, tgt in calls)


# ======================================================================
# Assignments
# ======================================================================


class TestAssignments:
    def test_simple_alias(self):
        source = "from mymod import MyClass\nx = MyClass\n"
        _, ctx = _extract(source)
        assert ctx.resolve("x") is not None

    def test_self_attr_type_hint(self):
        source = (
            "class Svc:\n"
            "    def __init__(self, repo: Repo):\n"
            "        self.repo = repo\n"
        )
        _, ctx = _extract(source)
        assert ctx.resolve_instance("self.repo") is not None

    def test_call_assigned_instance(self):
        source = (
            "class Svc:\n    pass\ndef make() -> Svc:\n    return Svc()\nx = make()\n"
        )
        _, ctx = _extract(source)
        assert ctx.resolve_instance("x") is not None

    def test_partial_alias(self):
        source = "from mymod import process\nhandler = partial(process)\n"
        _, ctx = _extract(source)
        resolved = ctx.resolve("handler")
        assert resolved is not None
        assert "process" in resolved

    def test_deep_chain_assignment(self):
        source = (
            "class Inner:\n    pass\n"
            "class Outer:\n"
            "    @property\n"
            "    def inner(self) -> Inner:\n        ...\n"
            "class Wrapper:\n"
            "    @property\n"
            "    def outer(self) -> Outer:\n        ...\n"
            "def run():\n"
            "    w = Wrapper()\n"
            "    x = w.outer.inner\n"
        )
        _, ctx = _extract(source)
        instance = ctx.resolve_instance("x")
        assert instance is not None
        assert "Inner" in instance

    def test_tuple_unpacking(self):
        source = (
            "class A:\n    pass\n"
            "class B:\n    pass\n"
            "def get_pair() -> tuple[A, B]:\n    ...\n"
            "a, b = get_pair()\n"
        )
        _, ctx = _extract(source)
        assert ctx.resolve("a") is not None
        assert ctx.resolve("b") is not None


# ======================================================================
# Type Resolution
# ======================================================================


class TestTypeResolution:
    def test_union_type(self):
        source = (
            "class A:\n    pass\nclass B:\n    pass\ndef foo(x: A | B):\n    pass\n"
        )
        _, ctx = _extract(source)
        union = ctx.union_targets("x")
        assert union is not None
        assert len(union) == 2

    def test_return_type_resolution(self):
        source = (
            "class Svc:\n    pass\ndef make() -> Svc:\n    return Svc()\nx = make()\n"
        )
        _, ctx = _extract(source)
        instance = ctx.resolve_instance("x")
        assert instance is not None
        assert "Svc" in instance


# ======================================================================
# Inheritance
# ======================================================================


class TestInheritance:
    def test_single_base(self):
        source = "class Base:\n    pass\nclass Child(Base):\n    pass\n"
        facts, _ = _extract(source)
        edges = _inherits(facts)
        assert len(edges) == 1
        src, tgt = next(iter(edges))
        assert "Child" in src
        assert "Base" in tgt

    def test_multiple_bases(self):
        source = "class A:\n    pass\nclass B:\n    pass\nclass C(A, B):\n    pass\n"
        facts, _ = _extract(source)
        edges = _inherits(facts)
        assert len(edges) == 2
        targets = {tgt for _, tgt in edges}
        assert any("A" in t for t in targets)
        assert any("B" in t for t in targets)


# ======================================================================
# With Statement
# ======================================================================


class TestWithStatement:
    def test_with_as_registers_instance(self):
        source = (
            "class Conn:\n    pass\n"
            "class Pool:\n"
            "    def __enter__(self) -> Conn:\n        ...\n"
            "def run():\n"
            "    with Pool() as conn:\n"
            "        conn.execute()\n"
        )
        facts, ctx = _extract(source)
        assert ctx.resolve_instance("conn") is not None


# ======================================================================
# Property
# ======================================================================


class TestProperty:
    def test_property_registers_class_attribute(self):
        source = (
            "class Svc:\n    pass\n"
            "class Repo:\n"
            "    @property\n"
            "    def service(self) -> Svc:\n"
            "        ...\n"
        )
        _, ctx = _extract(source)
        attr = ctx.resolve_class_attribute("Repo", "service")
        assert attr is not None
        assert "Svc" in attr
