"""Decorated definition lowering (CALLS from decorated symbol to decorators)."""

from __future__ import annotations

from coderay.graph.identifiers import caller_id_for_scope
from coderay.graph.lowering.session import LoweringSession
from coderay.graph.processors.callee_resolution import CalleeResolution
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class DecoratorProcessor:
    """Emit CALLS from decorated def/class to decorator callees."""

    def __init__(
        self,
        session: LoweringSession,
        parser: BaseTreeSitterParser,
        callee: CalleeResolution,
    ) -> None:
        self._session = session
        self._parser = parser
        self._callee = callee

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        """Record CALLS from decorated symbol to each decorator."""
        decorators: list[str] = []
        decorated_name: str | None = None
        for child in node.named_children:
            if child.type == "decorator":
                deco_text = _extract_decorator_name(self._parser, child)
                if deco_text:
                    decorators.append(deco_text)
            elif child.type in ("function_definition", "class_definition"):
                for cchild in child.named_children:
                    if cchild.type == "identifier":
                        decorated_name = self._parser.node_text(cchild).strip()
                        break
        if not decorators:
            return
        caller_scope = scope_stack + [decorated_name] if decorated_name else scope_stack
        caller_id = caller_id_for_scope(
            self._session.module_id, self._parser.file_path, caller_scope
        )
        for decorator in decorators:
            callee_targets = self._callee.resolve_callee_targets(decorator, scope_stack)
            self._callee.add_call_edges(caller_id, decorator, callee_targets)
        return None


def _extract_decorator_name(
    parser: BaseTreeSitterParser, decorator_node: TSNode
) -> str | None:
    """Extract name from decorator node (bare, dotted, or call form)."""
    for child in decorator_node.named_children:
        if child.type == "identifier":
            return parser.node_text(child).strip() or None
        if child.type in ("attribute", "member_expression"):
            return parser.node_text(child).strip() or None
        if child.type in parser.lang_cfg.cst.call_types:
            callee = child.child_by_field_name("function")
            if callee:
                return parser.node_text(callee).strip() or None
    return None
