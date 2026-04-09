"""Python with/as context manager instance typing (Pass 1)."""

from __future__ import annotations

from coderay.graph.handlers.typed_params import get_function_return_type
from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class PythonWithBinder:
    """Bind as-target names from __enter__ return type (Pass 1)."""

    def register(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None:
        del scope_stack
        for child in node.children:
            if child.type in ("with_clause", "with_clauses"):
                for item in child.children:
                    if item.type == "with_item":
                        self._process_with_item(item, parser, bindings)

    def _process_with_item(
        self,
        item: TSNode,
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None:
        value = item.child_by_field_name("value")
        if not value:
            return
        call_types = parser.lang_cfg.cst.call_types
        if value.type == "as_pattern":
            target_node = value.child_by_field_name("alias")
            call_node = next(
                (c for c in value.named_children if c.type in call_types), None
            )
        else:
            target_node = value if value.type == "as_pattern_target" else None
            call_node = value if value.type in call_types else None
        if not call_node or not target_node:
            return
        var_name = parser.node_text(target_node)
        if not var_name or var_name == "_":
            return
        callee_node = call_node.child_by_field_name("function")
        cm_name = parser.node_text(callee_node).strip() if callee_node else ""
        if not cm_name:
            return
        # with cm as x: "x" -> return type of cm.__enter__ (same ref shape as other instances).
        enter_return = get_function_return_type(
            parser, bindings, f"{cm_name}.__enter__"
        )
        if enter_return:
            bindings.register_instance(var_name, enter_return)
