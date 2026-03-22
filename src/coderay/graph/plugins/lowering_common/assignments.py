"""Assignment lowering shared across languages (portable alias/instance tracking)."""

from __future__ import annotations

from typing import Any

TSNode = Any


class AssignmentCoreMixin:
    """Track aliases and instance types from assignments (no Python-only patterns)."""

    def _get_assignment_sides(
        self, node: TSNode
    ) -> tuple[TSNode | None, TSNode | None]:
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

    def _handle_assignment(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Track aliases and instance types for call resolution."""
        lhs, rhs = self._get_assignment_sides(node)
        if lhs is None or rhs is None:
            return

        if lhs.type == "attribute" and rhs.type == "identifier":
            lhs_text = self.node_text(lhs)
            if lhs_text.startswith(("self.", "this.")):
                rhs_name = self.node_text(rhs)
                func_node = self._get_enclosing_function_node(node)
                if func_node:
                    type_hint = self._get_parameter_type_hint(func_node, rhs_name)
                    if type_hint:
                        self._file_ctx.register_instance(lhs_text, type_hint)
                        class_qualified = self._find_enclosing_class_from_node(
                            func_node
                        )
                        if class_qualified:
                            attr_name = lhs_text.split(".", 1)[1].split(".")[0]
                            self._file_ctx.register_class_attribute(
                                class_qualified, attr_name, type_hint
                            )
            return

        if lhs.type != "identifier":
            return

        lhs_name = self.node_text(lhs)

        if rhs.type == "identifier":
            rhs_name = self.node_text(rhs)
            resolved = self._file_ctx.resolve(rhs_name)
            if resolved:
                self._file_ctx.register_alias(lhs_name, resolved)
        elif rhs.type == "attribute":
            rhs_text = self.node_text(rhs)
            parts = rhs_text.split(".")
            if len(parts) == 2:
                prefix, attr = parts
                prefix_resolved = self._file_ctx.resolve(prefix)
                if prefix_resolved:
                    self._file_ctx.register_alias(
                        lhs_name, f"{prefix_resolved}::{attr}"
                    )
        elif rhs.type in self._ctx.lang_cfg.cst.call_types:
            self._register_assignment_from_call(lhs_name, rhs, node, scope_stack)

    def _register_assignment_from_call(
        self,
        lhs_name: str,
        rhs: TSNode,
        node: TSNode,
        scope_stack: list[str],
    ) -> None:
        """Register instance type from call return type."""
        del node, scope_stack
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self.node_text(callee_node).strip()
        if not callee_name:
            return
        return_type = self._get_function_return_type(callee_name)
        if return_type:
            self._file_ctx.register_instance(lhs_name, return_type)

    def _handle_with_statement(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Override in Python plugin for context managers."""
        del node, scope_stack
