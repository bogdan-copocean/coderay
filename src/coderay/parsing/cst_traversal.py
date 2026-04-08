"""Generic CST traversal helpers — config-driven, language-agnostic.

All functions take a ``BaseTreeSitterParser`` whose ``lang_cfg.cst`` supplies
the language-specific node-type sets (e.g. ``class_scope_types``,
``function_scope_types``).  No graph or binding dependencies — safe to import
from any layer.
"""

from __future__ import annotations

from coderay.parsing.base import BaseTreeSitterParser, TSNode


def find_class_node(parser: BaseTreeSitterParser, class_name: str) -> TSNode | None:
    """Find a class/struct definition node by name in the parsed tree."""
    class_types = parser.lang_cfg.cst.class_scope_types

    def search(n: TSNode) -> TSNode | None:
        if n.type in class_types:
            name_node = n.child_by_field_name("name") or (
                n.named_children[0] if n.named_children else None
            )
            if name_node and parser.node_text(name_node) == class_name:
                return n
        for c in n.children:
            found = search(c)
            if found:
                return found
        return None

    return search(parser.get_tree().root_node)


def find_top_level_function(parser: BaseTreeSitterParser, name: str) -> TSNode | None:
    """Find a module-scope function node by name."""
    fn_types = parser.lang_cfg.cst.function_scope_types

    def search(n: TSNode) -> TSNode | None:
        # identifier_from_node handles arrow functions (variable_declarator wrapping).
        if n.type in fn_types and parser.identifier_from_node(n) == name:
            return n
        for c in n.children:
            found = search(c)
            if found:
                return found
        return None

    return search(parser.get_tree().root_node)


def find_method_in_class(
    parser: BaseTreeSitterParser, class_name: str, method_name: str
) -> TSNode | None:
    """Find a method node inside a named class/struct."""
    class_node = find_class_node(parser, class_name)
    if not class_node:
        return None
    body_types = parser.lang_cfg.cst.class_body_types
    fn_types = parser.lang_cfg.cst.function_scope_types
    for child in class_node.children:
        if child.type not in body_types:
            continue
        for stmt in child.children:
            node = unwrap_decorated(stmt)
            if (
                node.type in fn_types
                and parser.identifier_from_node(node) == method_name
            ):
                return node
    return None


def find_enclosing_class_from_node(
    parser: BaseTreeSitterParser, node: TSNode
) -> str | None:
    """Walk up the CST and return the innermost enclosing class qualified name.

    e.g. node inside Outer.Inner  ->  "Outer.Inner"
    """
    current = node.parent
    class_names: list[str] = []
    class_scope_types = parser.lang_cfg.cst.class_scope_types
    while current:
        if current.type in class_scope_types:
            name_node = current.child_by_field_name("name") or (
                current.named_children[0] if current.named_children else None
            )
            if name_node:
                name = parser.node_text(name_node)
                if name:
                    class_names.append(name)
        current = current.parent
    if not class_names:
        return None
    class_names.reverse()  # collected inner-to-outer; reverse for qualified form
    return ".".join(class_names)


def get_enclosing_function_node(
    parser: BaseTreeSitterParser, node: TSNode
) -> TSNode | None:
    """Walk up the CST and return the innermost enclosing function node."""
    current = node.parent
    fn_types = parser.lang_cfg.cst.function_scope_types
    while current:
        if current.type in fn_types:
            return current
        current = current.parent
    return None


def unwrap_decorated(node: TSNode) -> TSNode:
    """Return the inner def/class from a decorated_definition, or node itself."""
    if node.type == "decorated_definition":
        for c in node.children:
            if c.type != "decorator":
                return c
    return node
