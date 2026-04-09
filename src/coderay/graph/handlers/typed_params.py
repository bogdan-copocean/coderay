"""Type-annotation resolution helpers for typed OOP languages (Python, TypeScript).

Combines CST traversal (parsing/cst_traversal) with annotation string parsing
(typed_annotations) and name bindings.  Not applicable to languages without
typed parameter syntax (Go, plain C).
"""

from __future__ import annotations

from coderay.graph.handlers.typed_annotations import (
    is_bare_self_annotation,
    resolve_annotation_type_texts,
)
from coderay.graph.lowering.name_bindings import NameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode
from coderay.parsing.cst_traversal import (
    find_enclosing_class_from_node,
    find_method_in_class,
    find_top_level_function,
)


def resolve_type_texts(
    parser: BaseTreeSitterParser,
    bindings: NameBindings,
    type_text: str | None,
    *,
    enclosing_func_node: TSNode | None = None,
) -> list[str]:
    """Resolve annotation text to qualified class refs.

    e.g. "Foo | Bar" -> ["path/a.py::Foo", "path/b.py::Bar"]
    """
    use_self = bool(enclosing_func_node) and is_bare_self_annotation(type_text)
    enc = (
        find_enclosing_class_from_node(parser, enclosing_func_node)
        if use_self
        else None
    )
    return resolve_annotation_type_texts(
        type_text,
        file_path=parser.file_path,
        resolve=bindings.resolve,
        use_self_semantics=use_self,
        enclosing_class_qualified=enc,
    )


def get_return_type_from_func_node(
    parser: BaseTreeSitterParser, bindings: NameBindings, func_node: TSNode
) -> str | None:
    """Read the return-type annotation of a function node and resolve it."""
    # Python uses "return_type", JS/TS uses "type".
    type_node = func_node.child_by_field_name(
        "return_type"
    ) or func_node.child_by_field_name("type")
    if not type_node:
        return None
    refs = resolve_type_texts(
        parser, bindings, parser.node_text(type_node), enclosing_func_node=func_node
    )
    return refs[0] if refs else None


def get_function_return_type(
    parser: BaseTreeSitterParser, bindings: NameBindings, callee_name: str
) -> str | None:
    """Look up a callee by name and return its annotated return type, or None."""
    if "." in callee_name:
        class_name, method_name = callee_name.split(".", 1)
        func_node = find_method_in_class(parser, class_name, method_name)
    else:
        func_node = find_top_level_function(parser, callee_name)
    return (
        get_return_type_from_func_node(parser, bindings, func_node)
        if func_node
        else None
    )


def extract_type_from_typed_param(
    parser: BaseTreeSitterParser, bindings: NameBindings, param_node: TSNode
) -> tuple[str, list[str]] | None:
    """Extract (param_name, type_refs) from a typed parameter CST node.

    e.g. `x: Foo` -> ("x", ["path/a.py::Foo"])
    """
    name_node = param_node.child_by_field_name("name") or (
        param_node.children[0] if param_node.children else None
    )
    if not name_node:
        return None
    pname = parser.node_text(name_node)
    type_node = param_node.child_by_field_name("type")
    if type_node is None:
        # Some grammars wrap the type under a bare "type" child instead of a field.
        for c in param_node.children:
            if c.type == "type":
                type_node = c
                break
    if not type_node:
        return None
    # param_node.parent = parameters, parameters.parent = function_definition.
    parent = param_node.parent
    enclosing = parent.parent if parent and parent.parent else None
    type_refs = resolve_type_texts(
        parser, bindings, parser.node_text(type_node), enclosing_func_node=enclosing
    )
    return (pname, type_refs) if type_refs else None


def get_typed_parameters(
    parser: BaseTreeSitterParser, bindings: NameBindings, func_node: TSNode
) -> list[tuple[str, list[str]]]:
    """Return (param_name, type_refs) for every typed parameter of a function."""
    params = func_node.child_by_field_name("parameters")
    if not params:
        return []
    param_types = parser.lang_cfg.cst.typed_param_types
    result: list[tuple[str, list[str]]] = []
    for child in params.children:
        if child.type in param_types:
            extracted = extract_type_from_typed_param(parser, bindings, child)
            if extracted:
                result.append(extracted)
    return result


def get_parameter_type_hint(
    parser: BaseTreeSitterParser,
    bindings: NameBindings,
    func_node: TSNode,
    param_name: str,
) -> str | None:
    """Return the first resolved type ref for a named parameter, or None."""
    for name, refs in get_typed_parameters(parser, bindings, func_node):
        if name == param_name:
            return refs[0] if refs else None
    return None
