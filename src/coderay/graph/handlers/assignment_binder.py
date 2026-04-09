"""Assignment lowering: alias and instance tracking (Pass 1)."""

from __future__ import annotations

from coderay.graph.handlers.typed_params import (
    get_function_return_type,
    get_parameter_type_hint,
)
from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode
from coderay.parsing.cst_traversal import (
    find_enclosing_class_from_node,
    get_enclosing_function_node,
)


def assignment_sides(node: TSNode) -> tuple[TSNode | None, TSNode | None]:
    """Return (lhs, rhs) for assignment-like nodes."""
    if node.type == "variable_declarator":
        return node.child_by_field_name("name"), node.child_by_field_name("value")
    if node.type == "assignment_expression":
        return node.child_by_field_name("left"), node.child_by_field_name("right")
    children = node.children
    if len(children) < 3:
        return None, None
    return children[0], children[-1]


class AssignmentBinder:
    """Track aliases and instance types from assignments (Pass 1)."""

    def register(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None:
        del scope_stack
        lhs, rhs = assignment_sides(node)
        if lhs is None or rhs is None:
            return
        self_prefix = parser.lang_cfg.graph.self_prefix
        nt = parser.node_text
        if lhs.type == "attribute":
            lhs_text = nt(lhs)
            if self_prefix and lhs_text.startswith(self_prefix):
                if rhs.type == "identifier":
                    rhs_name = nt(rhs)
                    func_node = get_enclosing_function_node(parser, node)
                    if func_node:
                        type_hint = get_parameter_type_hint(
                            parser, bindings, func_node, rhs_name
                        )
                        if type_hint:
                            # self.attr from param: "self.x" -> class ref.
                            bindings.register_instance(lhs_text, type_hint)
                            class_qualified = find_enclosing_class_from_node(
                                parser, func_node
                            )
                            if class_qualified:
                                attr_name = lhs_text.split(".", 1)[1].split(".")[0]
                                bindings.register_class_attribute(
                                    class_qualified, attr_name, type_hint
                                )
                elif rhs.type in parser.lang_cfg.cst.call_types:
                    # self.attr = SomeClass() — register instance type
                    callee_node = rhs.child_by_field_name("function")
                    if callee_node:
                        callee_name = nt(callee_node).strip()
                        callee_base = callee_name.rsplit(".", 1)[-1]
                        if callee_base and callee_base[0].isupper():
                            resolved = bindings.resolve(callee_base)
                            is_known = bindings.is_class(callee_base)
                            if is_known or resolved is not None:
                                class_ref = resolved or callee_base
                                # self.attr = Foo(): "self.attr" -> file::Foo or "Foo".
                                bindings.register_instance(lhs_text, class_ref)
                                func_node = get_enclosing_function_node(parser, node)
                                class_qualified = (
                                    find_enclosing_class_from_node(parser, func_node)
                                    if func_node
                                    else None
                                )
                                if class_qualified:
                                    attr_name = lhs_text.split(".", 1)[1].split(".")[0]
                                    bindings.register_class_attribute(
                                        class_qualified, attr_name, class_ref
                                    )
            return
        if lhs.type != "identifier":
            return
        lhs_name = nt(lhs)
        if rhs.type == "identifier":
            resolved = bindings.resolve(nt(rhs))
            if resolved:
                # a = b: "a" -> same binding target as "b".
                bindings.register_alias(lhs_name, resolved)
        elif rhs.type == "attribute":
            rhs_text = nt(rhs)
            parts = rhs_text.split(".")
            if len(parts) >= 2:
                chain_refs = bindings.resolve_chain(rhs_text)
                if chain_refs:
                    # a = x.y.z: "a" -> first resolved class ref.
                    bindings.register_instance(lhs_name, chain_refs[0])
                else:
                    prefix_resolved = bindings.resolve(parts[0])
                    if prefix_resolved:
                        # a = mod.sub: "a" -> prefix::sub.
                        bindings.register_alias(
                            lhs_name, f"{prefix_resolved}::{'.'.join(parts[1:])}"
                        )
        elif rhs.type in parser.lang_cfg.cst.call_types:
            self._register_from_call(lhs_name, rhs, bindings, parser)

    def _register_from_call(
        self,
        lhs_name: str,
        rhs: TSNode,
        bindings: FileNameBindings,
        parser: BaseTreeSitterParser,
    ) -> None:
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = parser.node_text(callee_node).strip()
        if not callee_name:
            return
        # Try annotation-based return type first.
        return_type = get_function_return_type(parser, bindings, callee_name)
        if return_type:
            bindings.register_instance(lhs_name, return_type)
            return
        # Fall back: treat capitalised names as constructor calls.
        callee_base = callee_name.rsplit(".", 1)[-1]
        if callee_base and callee_base[0].isupper():
            resolved = bindings.resolve(callee_base)
            if bindings.is_class(callee_base) or resolved is not None:
                bindings.register_instance(lhs_name, resolved or callee_base)
