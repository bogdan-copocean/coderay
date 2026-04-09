"""Python function binder — extends ``DefinitionBinder`` (typed params, @property)."""

from __future__ import annotations

from coderay.core.models import NodeKind
from coderay.graph.handlers.definition_binder import DefinitionBinder
from coderay.graph.handlers.typed_params import (
    get_return_type_from_func_node,
    get_typed_parameters,
)
from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class PythonFunctionBinder(DefinitionBinder):
    """DefinitionBinder extended with typed param and @property registration."""

    def __init__(self, module_id: str) -> None:
        super().__init__(module_id, NodeKind.FUNCTION)

    def register(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None:
        # Param "x" -> one class ref | union: "x" -> file::T or ["T","U"].
        for param_name, type_refs in get_typed_parameters(parser, bindings, node):
            if len(type_refs) == 1:
                bindings.register_instance(param_name, type_refs[0])
            else:
                bindings.register_instance_union(param_name, type_refs)

        if scope_stack and _is_property(parser, node):
            name = parser.identifier_from_node(node)
            return_type = get_return_type_from_func_node(parser, bindings, node)
            if name and return_type:
                # Key "ClsName.attr" (scope joined) -> return type ref.
                bindings.register_class_attribute(
                    ".".join(scope_stack), name, return_type
                )

        super().register(node, scope_stack, parser, bindings)


def _is_property(parser: BaseTreeSitterParser, func_node: TSNode) -> bool:
    parent = func_node.parent
    if parent is None or parent.type != "decorated_definition":
        return False
    return any(
        parser.node_text(child).strip().endswith("property")
        for child in parent.children
        if child.type == "decorator"
    )
