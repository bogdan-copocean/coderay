"""Assignment and with-statement handling for graph extraction."""

from __future__ import annotations

from typing import Any

TSNode = Any


class AssignmentHandlerMixin:
    """Handle assignments and with statements for instance/alias tracking."""

    def _get_assignment_sides(
        self, node: TSNode
    ) -> tuple[TSNode | None, TSNode | None]:
        """Return (lhs, rhs) for assignment-like nodes; (None, None) if not applicable."""
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

        # Constructor/setter injection: self.storage = storage (storage: StoragePort)
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

        # Tuple unpacking: a, b = get_pair()
        if lhs.type in ("pattern_list", "tuple_pattern", "list_pattern"):
            self._handle_tuple_unpacking(lhs, rhs)
            return

        if lhs.type != "identifier":
            return

        lhs_name = self.node_text(lhs)

        if rhs.type == "identifier":
            # Simple alias: my_func = imported_func
            rhs_name = self.node_text(rhs)
            resolved = self._file_ctx.resolve(rhs_name)
            if resolved:
                self._file_ctx.register_alias(lhs_name, resolved)
        elif rhs.type == "attribute":
            # x = obj.attr: alias when obj resolves (e.g. path_func = Path)
            rhs_text = self.node_text(rhs)
            parts = rhs_text.split(".")
            if len(parts) == 2:
                prefix, attr = parts
                prefix_resolved = self._file_ctx.resolve(prefix)
                if prefix_resolved:
                    self._file_ctx.register_alias(
                        lhs_name, f"{prefix_resolved}::{attr}"
                    )
        elif rhs.type in self._lc.call_types:
            # functools.partial: p = partial(foo, 1); p() → alias to foo
            callee_node = rhs.child_by_field_name("function")
            if callee_node:
                callee_name = self.node_text(callee_node).strip()
                if callee_name:
                    if callee_name == "partial" or callee_name.endswith(".partial"):
                        first_arg = self._get_first_call_arg(rhs)
                        if first_arg:
                            resolved = self._file_ctx.resolve(first_arg)
                            if resolved:
                                self._file_ctx.register_alias(lhs_name, resolved)
                        return
                    return_type = self._get_function_return_type(callee_name)
                    if return_type:
                        self._file_ctx.register_instance(lhs_name, return_type)

    def _handle_with_statement(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Track with cm() as var: register var with __enter__ return type."""
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
        # with x as y: value is as_pattern with alias; with x(): value is call
        if value.type == "as_pattern":
            target_node = value.child_by_field_name("alias")
            call_node = next(
                (c for c in value.named_children if c.type in self._lc.call_types),
                None,
            )
        else:
            # with x(): no "as" target — we don't register
            target_node = value if value.type == "as_pattern_target" else None
            call_node = value if value.type in self._lc.call_types else None
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
        # Collect identifiers from pattern_list
        identifiers: list[str] = []
        for child in lhs.children:
            if child.type == "identifier":
                name = self.node_text(child)
                if name and name != "_":
                    identifiers.append(name)
        if not identifiers:
            return

        # RHS must be a call
        if rhs.type not in self._lc.call_types:
            return
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self.node_text(callee_node).strip()
        if not callee_name:
            return

        # Get raw type text from function definition
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
