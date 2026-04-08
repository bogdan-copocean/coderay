"""Decorator lowering: CallsEdge from decorated symbol to decorators (Pass 2)."""

from __future__ import annotations

from coderay.graph.facts import CallsEdge, Fact
from coderay.graph.lowering.callee_resolver import CalleeResolver
from coderay.graph.lowering.cst_helpers import node_id
from coderay.graph.lowering.name_bindings import NameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class DecoratorEmitter:
    """Emit CallsEdge facts from decorated def/class to its decorators (Pass 2)."""

    def __init__(self, resolver: CalleeResolver) -> None:
        self._resolver = resolver

    def emit(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: NameBindings,
    ) -> list[Fact]:
        del bindings
        decorators: list[str] = []
        decorated_name: str | None = None
        for child in node.named_children:
            if child.type == "decorator":
                deco_text = _extract_decorator_name(parser, child)
                if deco_text:
                    decorators.append(deco_text)
            elif child.type in ("function_definition", "class_definition"):
                for cchild in child.named_children:
                    if cchild.type == "identifier":
                        decorated_name = parser.node_text(cchild).strip()
                        break
        if not decorators:
            return []
        if decorated_name:
            scope_stack.append(decorated_name)
        caller_id = node_id(parser.file_path, scope_stack)
        if decorated_name:
            scope_stack.pop()
        facts: list[Fact] = []
        for decorator in decorators:
            for target in self._resolver.resolve(decorator, scope_stack):
                if target:
                    facts.append(CallsEdge(source_id=caller_id, target=target))
        return facts


def _extract_decorator_name(
    parser: BaseTreeSitterParser, decorator_node: TSNode
) -> str | None:
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
