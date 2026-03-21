"""Resolver hooks: identity default until backends attach."""

from __future__ import annotations

from coderay.graph.facts import ModuleInfo
from coderay.graph.plugin_protocol import ProjectIndex
from coderay.graph.plugins.python import PythonGraphPlugin


def test_python_resolve_facts_identity():
    """Python plugin leaves facts unchanged (in-file resolution in extract)."""
    plugin = PythonGraphPlugin()
    facts = [ModuleInfo("a.py", 3)]
    out = plugin.resolve_facts(facts, ProjectIndex({}))
    assert out == facts
