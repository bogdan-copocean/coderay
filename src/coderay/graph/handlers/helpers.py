"""Graph handler helpers — only what needs both a parser and NameBindings."""

from __future__ import annotations

from coderay.graph.lowering.name_bindings import NameBindings


def resolve_base_class_name(raw: str, bindings: NameBindings) -> str:
    """Resolve a base class name through bindings.

    e.g. "mod.Base" -> "path/mod.py::Base".
    """
    parts = raw.split(".")
    if len(parts) == 1:
        return bindings.resolve(raw) or raw
    # Dotted: resolve the prefix module alias, keep the suffix as-is.
    prefix_resolved = bindings.resolve(parts[0])
    if prefix_resolved:
        return f"{prefix_resolved}.{'.'.join(parts[1:])}"
    return raw
