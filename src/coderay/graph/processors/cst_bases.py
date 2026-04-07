"""Base-class / heritage CST helpers shared by definition and call lowering."""

from __future__ import annotations

from collections.abc import Callable

from coderay.graph.file_context import FileContext
from coderay.parsing.base import TSNode


def list_base_names_from_arg_list(
    arg_list_node: TSNode, node_text: Callable[[TSNode], str]
) -> list[str]:
    # class Foo(Base, Mixin):  ->  ["Base", "Mixin"]
    base_types = (
        "identifier",
        "dotted_name",
        "attribute",
        "type_identifier",
        "member_expression",
    )
    result: list[str] = []
    candidates = arg_list_node.named_children
    if not candidates and arg_list_node.type in (
        "extends_clause",
        "class_heritage",
    ):
        value = arg_list_node.child_by_field_name("value")
        if value:
            candidates = [value]
    for arg in candidates:
        if arg.type in base_types:
            name = node_text(arg)
            if name:
                result.append(name)
        elif arg.type in ("generic_type", "subscript"):
            if arg.named_children:
                name = node_text(arg.named_children[0])
                if name:
                    result.append(name)
    return result


def resolve_base_class_name(raw: str, file_ctx: FileContext) -> str:
    """Resolve a base class identifier through import/alias state."""
    parts = raw.split(".")
    if len(parts) == 1:
        return file_ctx.resolve(raw) or raw
    prefix = parts[0]
    suffix = ".".join(parts[1:])
    prefix_resolved = file_ctx.resolve(prefix)
    if prefix_resolved:
        return f"{prefix_resolved}.{suffix}"
    return raw
