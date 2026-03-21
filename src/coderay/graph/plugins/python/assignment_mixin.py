"""Python-specific assignment lowering (unpack, partial, with)."""

from __future__ import annotations

from typing import Any

from coderay.graph.plugins.lowering_common.assignments import AssignmentCoreMixin

TSNode = Any


class PythonAssignmentMixin(AssignmentCoreMixin):
    """Handle pattern unpacking, functools.partial, and with/as."""

    def _handle_assignment(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Track aliases; include tuple unpack and defer to core for simple assigns."""
        lhs, rhs = self._get_assignment_sides(node)
        if lhs is None or rhs is None:
            return

        if lhs.type in ("pattern_list", "tuple_pattern", "list_pattern"):
            self._handle_tuple_unpacking(lhs, rhs)
            return

        super()._handle_assignment(node, scope_stack=scope_stack)

    def _register_assignment_from_call(
        self,
        lhs_name: str,
        rhs: TSNode,
        node: TSNode,
        scope_stack: list[str],
    ) -> None:
        """Resolve partial() and otherwise register from call return type."""
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self.node_text(callee_node).strip()
        if not callee_name:
            return
        if callee_name == "partial" or callee_name.endswith(".partial"):
            first_arg = self._get_first_call_arg(rhs)
            if first_arg:
                resolved = self._file_ctx.resolve(first_arg)
                if resolved:
                    self._file_ctx.register_alias(lhs_name, resolved)
            return
        super()._register_assignment_from_call(lhs_name, rhs, node, scope_stack)

    def _handle_with_statement(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Register with cm() as var from __enter__ return type."""
        del scope_stack
        for child in node.children:
            if child.type in ("with_clause", "with_clauses"):
                for item in child.children:
                    if item.type == "with_item":
                        self._process_with_item(item)

    def _process_with_item(self, item: TSNode) -> None:
        """Register as target with __enter__ return type."""
        value = item.child_by_field_name("value")
        if not value:
            return
        if value.type == "as_pattern":
            target_node = value.child_by_field_name("alias")
            call_node = next(
                (c for c in value.named_children if c.type in self._desc.call_types),
                None,
            )
        else:
            target_node = value if value.type == "as_pattern_target" else None
            call_node = value if value.type in self._desc.call_types else None
        if not call_node or not target_node:
            return
        var_name = self.node_text(target_node)
        if not var_name or var_name == "_":
            return
        callee_node = call_node.child_by_field_name("function")
        cm_name = self.node_text(callee_node).strip() if callee_node else ""
        if not cm_name:
            return
        enter_return = self._get_function_return_type(f"{cm_name}.__enter__")
        if enter_return:
            self._file_ctx.register_instance(var_name, enter_return)

    def _handle_tuple_unpacking(self, lhs: TSNode, rhs: TSNode) -> None:
        """Track a, b = func(); register from return type."""
        identifiers: list[str] = []
        for child in lhs.children:
            if child.type == "identifier":
                name = self.node_text(child)
                if name and name != "_":
                    identifiers.append(name)
        if not identifiers:
            return

        if rhs.type not in self._desc.call_types:
            return
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self.node_text(callee_node).strip()
        if not callee_name:
            return

        func_node = (
            self._find_method_in_class(*callee_name.split(".", 1))
            if "." in callee_name
            else self._find_top_level_function(callee_name)
        )
        if not func_node:
            return
        type_node = func_node.child_by_field_name(
            "return_type"
        ) or func_node.child_by_field_name("type")
        if not type_node:
            return

        type_args = self._extract_tuple_type_args(type_node)
        for i, name in enumerate(identifiers):
            if i < len(type_args):
                self._file_ctx.register_alias(name, type_args[i])

    def _get_first_call_arg(self, call_node: TSNode) -> str | None:
        """Extract first call arg identifier."""
        arg_list = call_node.child_by_field_name("arguments") or next(
            (c for c in call_node.children if c.type == "argument_list"), None
        )
        if not arg_list:
            return None
        for child in arg_list.named_children:
            if child.type in ("identifier", "dotted_name", "attribute"):
                return self.node_text(child)
        return None
