"""Assignment lowering (alias and instance tracking from assignments)."""

from __future__ import annotations

from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead
from coderay.graph.processors.type_lookup import TypeLookup
from coderay.parsing.base import TSNode


def _assignment_sides(node: TSNode) -> tuple[TSNode | None, TSNode | None]:
    """Return (lhs, rhs) for assignment-like nodes."""
    if node.type == "variable_declarator":
        lhs = node.child_by_field_name("name")
        rhs = node.child_by_field_name("value")
        return (lhs, rhs)
    if node.type == "assignment_expression":
        lhs = node.child_by_field_name("left")
        rhs = node.child_by_field_name("right")
        return (lhs, rhs)
    children = node.children
    if len(children) < 3:
        return (None, None)
    return (children[0], children[-1])


class AssignmentProcessor:
    """Track aliases and instance types from assignments."""

    def __init__(
        self,
        session: LoweringSession,
        syntax: SyntaxRead,
        type_lookup: TypeLookup,
    ) -> None:
        self._session = session
        self._syntax = syntax
        self._type_lookup = type_lookup

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        # x = y          ->  alias x to resolved(y)
        lhs, rhs = _assignment_sides(node)
        if lhs is None or rhs is None:
            return
        self_prefix = self._syntax.lang_cfg.graph.self_prefix
        nt = self._syntax.node_text
        fc = self._session.file_ctx
        if lhs.type == "attribute" and rhs.type == "identifier":
            lhs_text = nt(lhs)
            if self_prefix and lhs_text.startswith(self_prefix):
                rhs_name = nt(rhs)
                func_node = self._type_lookup.get_enclosing_function_node(node)
                if func_node:
                    type_hint = self._type_lookup.get_parameter_type_hint(
                        func_node, rhs_name
                    )
                    if type_hint:
                        fc.register_instance(lhs_text, type_hint)
                        tp = self._type_lookup
                        class_qualified = tp.find_enclosing_class_from_node(func_node)
                        if class_qualified:
                            attr_name = lhs_text.split(".", 1)[1].split(".")[0]
                            fc.register_class_attribute(
                                class_qualified, attr_name, type_hint
                            )
            return
        if lhs.type != "identifier":
            return
        lhs_name = nt(lhs)
        if rhs.type == "identifier":
            rhs_name = nt(rhs)
            resolved = fc.resolve(rhs_name)
            if resolved:
                fc.register_alias(lhs_name, resolved)
        elif rhs.type == "attribute":
            rhs_text = nt(rhs)
            parts = rhs_text.split(".")
            if len(parts) >= 2:
                chain_refs = fc.resolve_chain(rhs_text)
                if chain_refs:
                    fc.register_instance(lhs_name, chain_refs[0])
                else:
                    prefix = parts[0]
                    attr = ".".join(parts[1:])
                    prefix_resolved = fc.resolve(prefix)
                    if prefix_resolved:
                        fc.register_alias(lhs_name, f"{prefix_resolved}::{attr}")
        elif rhs.type in self._syntax.lang_cfg.cst.call_types:
            self._register_assignment_from_call(lhs_name, rhs, node, scope_stack)
        return None

    def _register_assignment_from_call(
        self,
        lhs_name: str,
        rhs: TSNode,
        node: TSNode,
        scope_stack: list[str],
    ) -> None:
        """Register instance from call return type."""
        del node, scope_stack
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self._syntax.node_text(callee_node).strip()
        if not callee_name:
            return
        return_type = self._type_lookup.get_function_return_type(callee_name)
        if return_type:
            self._session.file_ctx.register_instance(lhs_name, return_type)
