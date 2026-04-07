"""Python with/as context manager instance typing."""

from __future__ import annotations

from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead
from coderay.graph.processors.type_lookup import TypeLookup
from coderay.graph.processors.with_statement import WithStatementProcessor
from coderay.parsing.base import TSNode


class PythonWithStatementProcessor(WithStatementProcessor):
    """Bind as-target names from __enter__ return type."""

    def __init__(
        self,
        session: LoweringSession,
        syntax: SyntaxRead,
        type_lookup: TypeLookup,
    ) -> None:
        super().__init__(session, syntax, type_lookup)

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Register instances from with ... as bindings."""
        del scope_stack
        for child in node.children:
            if child.type in ("with_clause", "with_clauses"):
                for item in child.children:
                    if item.type == "with_item":
                        self._process_with_item(item)

    def _process_with_item(self, item: TSNode) -> None:
        """Type as-target from context manager __enter__ return."""
        value = item.child_by_field_name("value")
        if not value:
            return
        call_types = self._syntax._ctx.lang_cfg.cst.call_types
        if value.type == "as_pattern":
            target_node = value.child_by_field_name("alias")
            call_node = next(
                (c for c in value.named_children if c.type in call_types),
                None,
            )
        else:
            target_node = value if value.type == "as_pattern_target" else None
            call_node = value if value.type in call_types else None
        if not call_node or not target_node:
            return
        var_name = self._syntax.node_text(target_node)
        if not var_name or var_name == "_":
            return
        callee_node = call_node.child_by_field_name("function")
        cm_name = self._syntax.node_text(callee_node).strip() if callee_node else ""
        if not cm_name:
            return
        enter = f"{cm_name}.__enter__"
        enter_return = self._type_lookup.get_function_return_type(enter)
        if enter_return:
            self._session.file_ctx.register_instance(var_name, enter_return)
