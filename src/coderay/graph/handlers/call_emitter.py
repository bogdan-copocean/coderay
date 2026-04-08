"""Call-site lowering: CallsEdge facts (Pass 2)."""

from __future__ import annotations

from coderay.graph.facts import CallsEdge, Fact
from coderay.graph.lowering.callee_resolver import CalleeResolver
from coderay.graph.lowering.cst_helpers import node_id
from coderay.graph.lowering.name_bindings import NameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class CallEmitter:
    """Emit CallsEdge facts for call expressions (Pass 2)."""

    def __init__(self, resolver: CalleeResolver) -> None:
        self._resolver = resolver

    def emit(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: NameBindings,
    ) -> list[Fact]:
        del (
            bindings
        )  # resolution goes through the resolver which holds its own snapshot
        caller_id = node_id(parser.file_path, scope_stack)
        callee_node = node.child_by_field_name("function")
        if callee_node is None:
            return []
        raw_callee = parser.node_text(callee_node)
        if not raw_callee:
            return []
        targets = self._resolver.resolve(raw_callee, scope_stack)
        return [CallsEdge(source_id=caller_id, target=t) for t in targets if t]
