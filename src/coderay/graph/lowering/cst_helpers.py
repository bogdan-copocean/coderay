"""CST helpers used by lowering — no handlers/ dependency."""

from __future__ import annotations

from collections.abc import Callable

from coderay.parsing.base import TSNode


def node_id(
    file_path: str,
    scope_stack: list[str],
    name: str | None = None,
) -> str:
    """Canonical node ID from a file path, scope stack, and optional name.

    With name:    ("a.py", ["Foo"], "bar")  -> "a.py::Foo.bar"
    Without name: ("a.py", ["Foo"])         -> "a.py::Foo"
    Module scope: ("a.py", [])              -> "a.py"
    """
    parts = [*scope_stack, name] if name else scope_stack
    return f"{file_path}::{'.'.join(parts)}" if parts else file_path


# Node types that carry superclass lists — differs across languages:
# Python: argument_list / superclass  |  JS/TS: extends_clause / class_heritage
BASE_CLASS_NODE_TYPES = (
    "argument_list",
    "superclass",
    "extends_clause",
    "class_heritage",
)


def list_base_names_from_arg_list(
    arg_list_node: TSNode, node_text: Callable[[TSNode], str]
) -> list[str]:
    # class Foo(Base, Mixin)  ->  ["Base", "Mixin"]
    base_types = (
        "identifier",
        "dotted_name",
        "attribute",
        "type_identifier",
        "member_expression",
    )
    result: list[str] = []
    candidates = arg_list_node.named_children
    # JS/TS extends_clause / class_heritage store the value under a field.
    if not candidates and arg_list_node.type in ("extends_clause", "class_heritage"):
        value = arg_list_node.child_by_field_name("value")
        if value:
            candidates = [value]
    for arg in candidates:
        if arg.type in base_types:
            name = node_text(arg)
            if name:
                result.append(name)
        elif arg.type in ("generic_type", "subscript"):
            # Generic base: List[T] or Base[T]  ->  take the outer name only.
            if arg.named_children:
                name = node_text(arg.named_children[0])
                if name:
                    result.append(name)
    return result
