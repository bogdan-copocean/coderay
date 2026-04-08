"""Definition emission: SymbolDefinition and InheritsEdge facts (Pass 2)."""

from __future__ import annotations

from coderay.core.models import NodeKind
from coderay.graph.facts import Fact, InheritsEdge, SymbolDefinition
from coderay.graph.handlers.helpers import (
    BASE_CLASS_NODE_TYPES,
    list_base_names_from_arg_list,
    resolve_base_class_name,
)
from coderay.graph.lowering.name_bindings import NameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class DefinitionEmitter:
    """Emit SymbolDefinition (and InheritsEdge for classes) facts (Pass 2).

    Also appends the definition name to ``scope_stack`` so the DFS recurses
    into the body with the correct caller scope.
    """

    def __init__(self, module_id: str, kind: NodeKind) -> None:
        self._module_id = module_id
        self._kind = kind

    def emit(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: NameBindings,
    ) -> list[Fact]:
        name = parser.identifier_from_node(node)
        if not name:
            return []
        fp = parser.file_path
        qualified = ".".join([*scope_stack, name])
        definer = (
            self._module_id if not scope_stack else f"{fp}::{'.'.join(scope_stack)}"
        )
        node_id = f"{fp}::{qualified}"
        facts: list[Fact] = [
            SymbolDefinition(
                file_path=fp,
                scope_stack=tuple(scope_stack),
                name=name,
                kind=self._kind,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                definer_id=definer,
            )
        ]
        if self._kind == NodeKind.CLASS:
            for child in node.children:
                if child.type not in BASE_CLASS_NODE_TYPES:
                    continue
                for base_name in list_base_names_from_arg_list(child, parser.node_text):
                    facts.append(
                        InheritsEdge(
                            source_id=node_id,
                            target=resolve_base_class_name(base_name, bindings),
                        )
                    )
        scope_stack.append(name)
        return facts
