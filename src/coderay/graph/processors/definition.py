"""Class and function definition lowering (symbols and inheritance)."""

from __future__ import annotations

from coderay.core.models import NodeKind
from coderay.graph._utils import _BASE_CLASS_NODE_TYPES
from coderay.graph.facts import InheritsEdge, SymbolDefinition
from coderay.graph.lowering.session import LoweringSession
from coderay.graph.processors.cst_bases import (
    list_base_names_from_arg_list,
    resolve_base_class_name,
)
from coderay.parsing.base import BaseTreeSitterParser, TSNode


def _process_definition(
    session: LoweringSession,
    parser: BaseTreeSitterParser,
    node: TSNode,
    *,
    scope_stack: list[str],
    kind: NodeKind,
) -> str | None:
    """Emit symbol fact; return the scope name, or None if name missing."""
    name = parser.identifier_from_node(node)
    if not name:
        return None
    fp = parser.file_path
    qualified = ".".join([*scope_stack, name])
    definer = session.module_id if not scope_stack else f"{fp}::{'.'.join(scope_stack)}"
    node_id = f"{fp}::{qualified}"
    session.facts.add(
        SymbolDefinition(
            file_path=fp,
            scope_stack=tuple(scope_stack),
            name=name,
            kind=kind,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            definer_id=definer,
        )
    )
    fc = session.file_ctx
    if kind == NodeKind.CLASS:
        for child in node.children:
            if child.type not in _BASE_CLASS_NODE_TYPES:
                continue
            for base_name in list_base_names_from_arg_list(child, parser.node_text):
                session.facts.add(
                    InheritsEdge(
                        source_id=node_id,
                        target=resolve_base_class_name(base_name, fc),
                    )
                )
        fc.register_definition(name, node_id, is_class=True)
    else:
        fc.register_definition(qualified if scope_stack else name, node_id)
    return name


class FunctionDefinitionProcessor:
    """Emit function symbol; return scope name so DFS recurses under it."""

    def __init__(self, session: LoweringSession, parser: BaseTreeSitterParser) -> None:
        self._session = session
        self._parser = parser

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        return _process_definition(
            self._session,
            self._parser,
            node,
            scope_stack=scope_stack,
            kind=NodeKind.FUNCTION,
        )


class ClassDefinitionProcessor:
    """Emit class symbol and INHERITS edges; return scope name so DFS recurses."""

    def __init__(self, session: LoweringSession, parser: BaseTreeSitterParser) -> None:
        self._session = session
        self._parser = parser

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        return _process_definition(
            self._session,
            self._parser,
            node,
            scope_stack=scope_stack,
            kind=NodeKind.CLASS,
        )
