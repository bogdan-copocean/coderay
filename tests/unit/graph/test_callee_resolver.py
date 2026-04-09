"""Tests for CalleeResolver on Python snippets (same bindings as extraction)."""

from __future__ import annotations

from coderay.graph.extractors.python.extractor import PythonGraphExtractor
from coderay.graph.lowering.callee_resolver import CalleeResolver
from coderay.graph.lowering.callee_strategy import default_callee_strategy
from coderay.parsing.base import BaseTreeSitterParser, get_parse_context


def _resolver(
    source: str,
    path: str = "t.py",
    *,
    module_index: dict[str, str] | None = None,
) -> tuple[CalleeResolver, BaseTreeSitterParser]:
    """Run full extract, return (CalleeResolver, parser)."""
    ctx = get_parse_context(path, source)
    assert ctx is not None
    ext = (
        PythonGraphExtractor(ctx, module_index=module_index)
        if module_index
        else PythonGraphExtractor(ctx)
    )
    ext.extract_facts_list()
    res = default_callee_strategy(ext._file_ctx, ext._parser)
    return res, ext._parser


class TestCalleeResolverPython:
    """resolve(raw, scope_stack) invariants for Python."""

    def test_simple_name_resolves_import(self) -> None:
        """Imported name maps to binding target."""
        r, _ = _resolver("from os.path import join\n\ndef use():\n    join('a', 'b')\n")
        out = r.resolve("join", ["use"])
        assert len(out) == 1
        assert "join" in out[0]

    def test_simple_name_unresolved_is_phantom(self) -> None:
        """Unknown callee passes through as raw."""
        r, _ = _resolver("def f():\n    unknown()\n")
        assert r.resolve("unknown", ["f"]) == ["unknown"]

    def test_self_method_targets_class_member(self) -> None:
        """self.m in a method resolves to file::Class.m."""
        path = "t.py"
        r, _ = _resolver(
            "class Svc:\n"
            "    def run(self):\n"
            "        self.helper()\n"
            "    def helper(self):\n"
            "        pass\n",
            path,
        )
        out = r.resolve("self.helper", ["Svc", "run"])
        assert len(out) == 1
        assert out[0].startswith(path)
        assert out[0].endswith("Svc.helper")

    def test_super_delegates_to_base_method(self) -> None:
        """super().m resolves to base.method style target."""
        r, _ = _resolver(
            "class Base:\n"
            "    def process(self):\n"
            "        pass\n"
            "class Child(Base):\n"
            "    def run(self):\n"
            "        super().process()\n"
        )
        out = r.resolve("super().process", ["Child", "run"])
        assert len(out) == 1
        assert "process" in out[0]
        assert "Base" in out[0] or "base" in out[0].lower()

    def test_chain_instance_method(self) -> None:
        """obj.method uses instance typing from assignment."""
        r, _ = _resolver(
            "class Svc:\n"
            "    def work(self):\n"
            "        pass\n"
            "def f():\n"
            "    x = Svc()\n"
            "    x.work()\n"
        )
        out = r.resolve("x.work", ["f"])
        assert len(out) >= 1
        assert any("work" in t for t in out)

    def test_instance_name_resolves_to_dunder_call(self) -> None:
        """Calling an instance variable uses __call__ on the inferred class."""
        r, _ = _resolver(
            "class C:\n"
            "    def __call__(self):\n"
            "        pass\n"
            "def f():\n"
            "    x = C()\n"
            "    x()\n"
        )
        out = r.resolve("x", ["f"])
        assert len(out) == 1
        assert "__call__" in out[0]

    def test_chain_three_segments_uses_resolve_chain(self) -> None:
        """obj.attr.method walks instance typing for multi-segment chains."""
        r, _ = _resolver(
            "class Inner:\n"
            "    def leaf(self):\n"
            "        pass\n"
            "class Outer:\n"
            "    def __init__(self):\n"
            "        self.inner = Inner()\n"
            "def use():\n"
            "    o = Outer()\n"
            "    o.inner.leaf()\n"
        )
        out = r.resolve("o.inner.leaf", ["use"])
        assert out == ["t.py::Inner.leaf"]

    def test_self_chained_attr_resolves_instance_method(self) -> None:
        """self.repo.fetch uses instance + attribute typing on self.repo."""
        r, _ = _resolver(
            "class Repo:\n"
            "    def fetch(self):\n"
            "        pass\n"
            "class Svc:\n"
            "    def __init__(self):\n"
            "        self.repo = Repo()\n"
            "    def run(self):\n"
            "        self.repo.fetch()\n"
        )
        out = r.resolve("self.repo.fetch", ["Svc", "run"])
        assert len(out) == 1
        assert out[0].endswith("Repo.fetch")

    def test_super_without_base_returns_bare_method(self) -> None:
        """super() with no superclass leaves the method name as phantom."""
        r, _ = _resolver("class Lonely:\n    def m(self):\n        super().x()\n")
        assert r.resolve("super().x", ["Lonely", "m"]) == ["x"]

    def test_super_dot_prefix_same_as_super_call(self) -> None:
        """super. prefix matches second super_prefix and resolves like super()."""
        r, _ = _resolver(
            "class Base:\n"
            "    def process(self):\n"
            "        pass\n"
            "class Child(Base):\n"
            "    def run(self):\n"
            "        super().process()\n"
        )
        dot = r.resolve("super.process", ["Child", "run"])
        paren = r.resolve("super().process", ["Child", "run"])
        assert dot == paren
        assert len(dot) == 1
        assert "process" in dot[0]

    def test_imported_module_path_call_uses_file_qual(self) -> None:
        """Resolved module file path + member uses file::symbol target shape."""
        r, _ = _resolver(
            "import x\n\ndef f():\n    x.run()\n",
            module_index={"x": "lib/mod.py"},
        )
        out = r.resolve("x.run", ["f"])
        assert out == ["lib/mod.py::run"]
