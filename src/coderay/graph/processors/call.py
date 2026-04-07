"""Call-site lowering (CALLS facts and constructor instantiation tracking)."""

from __future__ import annotations

from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead
from coderay.graph.processors.callee_resolution import CalleeResolution
from coderay.graph.processors.scope import caller_id_for_scope
from coderay.graph.processors.type_lookup import TypeLookup
from coderay.parsing.base import TSNode


class CallProcessor:
    """Emit CALLS edges and track constructor instantiations."""

    def __init__(
        self,
        session: LoweringSession,
        syntax: SyntaxRead,
        type_lookup: TypeLookup,
        callee: CalleeResolution,
    ) -> None:
        self._session = session
        self._syntax = syntax
        self._type_lookup = type_lookup
        self._callee = callee

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Emit CALLS for a call expression."""
        caller_id = caller_id_for_scope(self._session, self._syntax, scope_stack)
        callee_node = node.child_by_field_name("function")
        if callee_node is None:
            return
        raw_callee = self._syntax.node_text(callee_node)
        if not raw_callee:
            return
        callee_targets = self._callee.resolve_callee_targets(raw_callee, scope_stack)
        self._callee.add_call_edges(caller_id, raw_callee, callee_targets)
        self._maybe_track_instantiation(node, raw_callee)

    def _maybe_track_instantiation(self, call_node: TSNode, raw_callee: str) -> None:
        """Register lhs as instance when rhs is a constructor call."""
        parent = call_node.parent
        atypes = self._syntax._ctx.lang_cfg.cst.assignment_types
        if parent is None or parent.type not in atypes:
            return
        lhs = (
            parent.child_by_field_name("name")
            or parent.child_by_field_name("left")
            or (parent.children[0] if parent.children else None)
        )
        if lhs is None:
            return
        self_prefix = self._syntax._ctx.lang_cfg.graph.self_prefix
        nt = self._syntax.node_text
        if lhs.type == "identifier":
            var_name = nt(lhs)
        elif lhs.type == "attribute":
            var_name = nt(lhs)
            if not self_prefix or not var_name.startswith(self_prefix):
                return
        else:
            return
        fc = self._session.file_ctx
        if fc.resolve_instance(var_name):
            return
        callee_base = raw_callee.rsplit(".", 1)[-1]
        if not callee_base:
            return
        resolved = fc.resolve(callee_base)
        is_known_class = fc.is_class(callee_base)
        is_likely_class = bool(callee_base[0].isupper() and resolved is not None)
        if is_known_class or is_likely_class:
            fc.register_instance(var_name, resolved or callee_base)
            if self_prefix and var_name.startswith(self_prefix):
                func_node = self._type_lookup.get_enclosing_function_node(call_node)
                if func_node:
                    class_qualified = self._type_lookup.find_enclosing_class_from_node(
                        func_node
                    )
                    if class_qualified:
                        attr_name = var_name.split(".", 1)[1].split(".")[0]
                        fc.register_class_attribute(
                            class_qualified, attr_name, resolved or callee_base
                        )
