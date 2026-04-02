"""Assignment lowering (alias and instance tracking from assignments)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coderay.parsing.base import TSNode

if TYPE_CHECKING:
    from coderay.graph.file_context import FileContext
    from coderay.parsing.base import ParserContext


class AssignmentMixin:
    """Track aliases and instance types from assignments."""

    _ctx: ParserContext
    _file_ctx: FileContext

    if TYPE_CHECKING:

        def node_text(self, node: Any) -> str: ...
        def _get_enclosing_function_node(self, node: Any) -> Any | None: ...
        def _get_parameter_type_hint(
            self, func_node: Any, param_name: str
        ) -> str | None: ...
        def _find_enclosing_class_from_node(self, node: Any) -> str | None: ...
        def _get_function_return_type(self, name: str) -> str | None: ...

    def _get_assignment_sides(
        self, node: TSNode
    ) -> tuple[TSNode | None, TSNode | None]:
        # x = foo  |  const x = foo  |  x = foo()
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
        # x = y          ->  alias x to resolved(y)
        # self.x = y     ->  register instance from type hint
        # x = a.b.c      ->  resolve chain or alias to prefix
        # x = foo()      ->  register instance from return type
        """Track aliases and instance types for call resolution."""
        lhs, rhs = self._get_assignment_sides(node)
        if lhs is None or rhs is None:
            return

        # Case 1: self.repo = repo — wire attribute type from constructor param hint
        # e.g. def __init__(self, repo: UserRepository) → self.repo is UserRepository
        self_prefix = self._ctx.lang_cfg.graph.self_prefix
        if lhs.type == "attribute" and rhs.type == "identifier":
            lhs_text = self.node_text(lhs)
            if self_prefix and lhs_text.startswith(self_prefix):
                rhs_name = self.node_text(rhs)
                func_node = self._get_enclosing_function_node(node)
                if func_node:
                    type_hint = self._get_parameter_type_hint(func_node, rhs_name)
                    if type_hint:
                        # Track both the instance and the class-level attribute
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

        # Only track simple identifier assignments (not destructuring, subscripts, etc.)
        if lhs.type != "identifier":
            return

        lhs_name = self.node_text(lhs)

        # Case 2: x = y — alias x to whatever y resolves to (import, definition, ...)
        if rhs.type == "identifier":
            rhs_name = self.node_text(rhs)
            resolved = self._file_ctx.resolve(rhs_name)
            if resolved:
                self._file_ctx.register_alias(lhs_name, resolved)
        # Case 3: x = w.outer.inner -> try full chain type resolution first
        # e.g. w is Wrapper, Wrapper.outer -> Outer, Outer.inner -> Inner => x is Inner
        # Falls back to prefix alias: x = mod.attr -> resolve mod, alias x to mod::attr
        elif rhs.type == "attribute":
            rhs_text = self.node_text(rhs)
            parts = rhs_text.split(".")
            if len(parts) >= 2:
                chain_refs = self._file_ctx.resolve_chain(rhs_text)
                if chain_refs:
                    self._file_ctx.register_instance(lhs_name, chain_refs[0])
                else:
                    prefix = parts[0]
                    attr = ".".join(parts[1:])
                    prefix_resolved = self._file_ctx.resolve(prefix)
                    if prefix_resolved:
                        self._file_ctx.register_alias(
                            lhs_name, f"{prefix_resolved}::{attr}"
                        )
        # Case 4: x = foo() — infer type from call return annotation
        elif rhs.type in self._ctx.lang_cfg.cst.call_types:
            self._register_assignment_from_call(lhs_name, rhs, node, scope_stack)

    def _register_assignment_from_call(
        self,
        lhs_name: str,
        rhs: TSNode,
        node: TSNode,
        scope_stack: list[str],
    ) -> None:
        # x = get_service()  ->  register x as instance of return type
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
        """Override in language subclass for context manager support."""
        del node, scope_stack
