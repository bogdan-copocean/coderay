"""Python-specific assignment: tuple unpack and partial() (Pass 1)."""

from __future__ import annotations

from coderay.graph.handlers.assignment_binder import AssignmentBinder, assignment_sides
from coderay.graph.handlers.typed_params import resolve_type_texts
from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode
from coderay.parsing.cst_traversal import find_method_in_class, find_top_level_function


class PythonAssignmentBinder(AssignmentBinder):
    """Extends AssignmentBinder with tuple unpack and partial() support."""

    def register(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None:
        lhs, rhs = assignment_sides(node)
        if lhs is None or rhs is None:
            return
        if lhs.type in ("pattern_list", "tuple_pattern", "list_pattern"):
            self._handle_tuple_unpacking(lhs, rhs, bindings, parser)
            return
        super().register(node, scope_stack, parser, bindings)

    def _register_from_call(
        self,
        lhs_name: str,
        rhs: TSNode,
        bindings: FileNameBindings,
        parser: BaseTreeSitterParser,
    ) -> None:
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = parser.node_text(callee_node).strip()
        if not callee_name:
            return
        if callee_name == "partial" or callee_name.endswith(".partial"):
            first_arg = self._get_first_call_arg(rhs, parser)
            if first_arg:
                resolved = bindings.resolve(first_arg)
                if resolved:
                    # p = partial(f, ...): "p" -> same target as bound callable "f".
                    bindings.register_alias(lhs_name, resolved)
            return
        super()._register_from_call(lhs_name, rhs, bindings, parser)

    def _handle_tuple_unpacking(
        self,
        lhs: TSNode,
        rhs: TSNode,
        bindings: FileNameBindings,
        parser: BaseTreeSitterParser,
    ) -> None:
        identifiers: list[str] = []
        for child in lhs.children:
            if child.type == "identifier":
                name = parser.node_text(child)
                if name and name != "_":
                    identifiers.append(name)
        if not identifiers:
            return
        if rhs.type not in parser.lang_cfg.cst.call_types:
            return
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = parser.node_text(callee_node).strip()
        if not callee_name:
            return
        func_node = (
            find_method_in_class(parser, *callee_name.split(".", 1))
            if "." in callee_name
            else find_top_level_function(parser, callee_name)
        )
        if not func_node:
            return
        type_node = func_node.child_by_field_name(
            "return_type"
        ) or func_node.child_by_field_name("type")
        if not type_node:
            return
        type_args = self._extract_tuple_type_args(type_node, parser, bindings)
        for i, name in enumerate(identifiers):
            if i < len(type_args):
                # a,b = t(): "a" -> Tuple type arg i (resolved ref string).
                bindings.register_alias(name, type_args[i])

    def _extract_tuple_type_args(
        self,
        type_node: TSNode,
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> list[str]:
        if type_node.type == "type" and type_node.named_children:
            type_node = type_node.named_children[0]
        if type_node.type != "generic_type":
            return []
        children = type_node.named_children
        if len(children) < 2:
            return []
        if parser.node_text(children[0]).lower() != "tuple":
            return []
        result: list[str] = []
        for type_child in children[1].named_children:
            if type_child.type == "type":
                refs = resolve_type_texts(
                    parser, bindings, parser.node_text(type_child)
                )
                result.extend(refs)
        return result

    def _get_first_call_arg(
        self, call_node: TSNode, parser: BaseTreeSitterParser
    ) -> str | None:
        arg_list = call_node.child_by_field_name("arguments") or next(
            (c for c in call_node.children if c.type == "argument_list"), None
        )
        if not arg_list:
            return None
        for child in arg_list.named_children:
            if child.type in ("identifier", "dotted_name", "attribute"):
                return parser.node_text(child)
        return None
