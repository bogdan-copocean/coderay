"""Python-specific assignment, tuple unpack, with/as, and partial()."""

from __future__ import annotations

from coderay.graph.lowering.session import LoweringSession
from coderay.graph.processors.assignment import AssignmentProcessor, _assignment_sides
from coderay.graph.processors.type_lookup import TypeLookup
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class PythonAssignmentProcessor(AssignmentProcessor):
    """Python tuple unpack, with/as, and partial() on top of base assignment rules."""

    def __init__(
        self,
        session: LoweringSession,
        parser: BaseTreeSitterParser,
        type_lookup: TypeLookup,
    ) -> None:
        super().__init__(session, parser, type_lookup)

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        """Python tuple unpack and base assignment rules."""
        lhs, rhs = _assignment_sides(node)
        if lhs is None or rhs is None:
            return
        if lhs.type in ("pattern_list", "tuple_pattern", "list_pattern"):
            self._handle_tuple_unpacking(lhs, rhs)
            return None
        return super().handle(node, scope_stack=scope_stack)

    def _register_assignment_from_call(
        self,
        lhs_name: str,
        rhs: TSNode,
        node: TSNode,
        scope_stack: list[str],
    ) -> None:
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self._parser.node_text(callee_node).strip()
        if not callee_name:
            return
        if callee_name == "partial" or callee_name.endswith(".partial"):
            first_arg = self._get_first_call_arg(rhs)
            if first_arg:
                resolved = self._session.file_ctx.resolve(first_arg)
                if resolved:
                    self._session.file_ctx.register_alias(lhs_name, resolved)
            return
        super()._register_assignment_from_call(lhs_name, rhs, node, scope_stack)

    def _handle_tuple_unpacking(self, lhs: TSNode, rhs: TSNode) -> None:
        """Bind names from tuple[A, B] return when unpacking a call."""
        identifiers: list[str] = []
        for child in lhs.children:
            if child.type == "identifier":
                name = self._parser.node_text(child)
                if name and name != "_":
                    identifiers.append(name)
        if not identifiers:
            return
        if rhs.type not in self._parser.lang_cfg.cst.call_types:
            return
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self._parser.node_text(callee_node).strip()
        if not callee_name:
            return
        func_node = (
            self._type_lookup.find_method_in_class(*callee_name.split(".", 1))
            if "." in callee_name
            else self._type_lookup.find_top_level_function(callee_name)
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
                self._session.file_ctx.register_alias(name, type_args[i])

    def _extract_tuple_type_args(self, type_node: TSNode) -> list[str]:
        """Expand tuple[...] generic into qualified refs."""
        if type_node.type == "type" and type_node.named_children:
            type_node = type_node.named_children[0]
        if type_node.type != "generic_type":
            return []
        children = type_node.named_children
        if len(children) < 2:
            return []
        base_name = self._parser.node_text(children[0])
        if base_name.lower() != "tuple":
            return []
        type_param_node = children[1]
        result: list[str] = []
        for type_child in type_param_node.named_children:
            if type_child.type == "type":
                ttext = self._parser.node_text(type_child)
                refs = self._type_lookup.resolve_type_texts(ttext)
                result.extend(refs)
        return result

    def _get_first_call_arg(self, call_node: TSNode) -> str | None:
        arg_list = call_node.child_by_field_name("arguments") or next(
            (c for c in call_node.children if c.type == "argument_list"), None
        )
        if not arg_list:
            return None
        for child in arg_list.named_children:
            if child.type in ("identifier", "dotted_name", "attribute"):
                return self._parser.node_text(child)
        return None
