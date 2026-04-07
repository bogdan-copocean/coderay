"""Class and function definition lowering (symbols and inheritance)."""

from __future__ import annotations

from collections.abc import Callable

from coderay.core.models import NodeKind
from coderay.graph._utils import _BASE_CLASS_NODE_TYPES
from coderay.graph.facts import InheritsEdge, SymbolDefinition
from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead
from coderay.graph.processors.cst_bases import (
    list_base_names_from_arg_list,
    resolve_base_class_name,
)
from coderay.parsing.base import TSNode


def _process_definition(
    session: LoweringSession,
    syntax: SyntaxRead,
    walk: Callable[[TSNode, list[str]], None],
    after_function_registered: Callable[[TSNode, list[str]], None] | None,
    node: TSNode,
    *,
    scope_stack: list[str],
    kind: NodeKind,
) -> None:
    """Record symbol; recurse into body."""
    name = syntax.identifier_from_node(node)
    if not name:
        return
    fp = syntax.file_path
    qualified = ".".join([*scope_stack, name])
    definer = session.module_id
    if scope_stack:
        definer = f"{fp}::{'.'.join(scope_stack)}"
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
    is_class = kind == NodeKind.CLASS
    fc = session.file_ctx
    nt = syntax.node_text
    if is_class:
        for child in node.children:
            if child.type not in _BASE_CLASS_NODE_TYPES:
                continue
            for base_name in list_base_names_from_arg_list(child, nt):
                resolved = resolve_base_class_name(base_name, fc)
                session.facts.add(InheritsEdge(source_id=node_id, target=resolved))
        fc.register_definition(name, node_id, is_class=True)
    else:
        if not scope_stack:
            fc.register_definition(name, node_id)
        else:
            fc.register_definition(qualified, node_id)
        if after_function_registered is not None:
            after_function_registered(node, scope_stack)
    new_scope = [*scope_stack, name]
    for child in node.children:
        walk(child, new_scope)


class FunctionDefinitionProcessor:
    """Emit function symbol definitions; recurse into body."""

    def __init__(
        self,
        session: LoweringSession,
        syntax: SyntaxRead,
        walk: Callable[[TSNode, list[str]], None],
        *,
        after_function_registered: Callable[[TSNode, list[str]], None] | None = None,
    ) -> None:
        self._session = session
        self._syntax = syntax
        self._walk = walk
        self._after_function_registered = after_function_registered

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Record function symbol; recurse into body."""
        _process_definition(
            self._session,
            self._syntax,
            self._walk,
            self._after_function_registered,
            node,
            scope_stack=scope_stack,
            kind=NodeKind.FUNCTION,
        )


class ClassDefinitionProcessor:
    """Emit class symbol definitions and INHERITS edges; recurse into body."""

    def __init__(
        self,
        session: LoweringSession,
        syntax: SyntaxRead,
        walk: Callable[[TSNode, list[str]], None],
    ) -> None:
        self._session = session
        self._syntax = syntax
        self._walk = walk

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Record class symbol and bases; recurse into body."""
        _process_definition(
            self._session,
            self._syntax,
            self._walk,
            None,
            node,
            scope_stack=scope_stack,
            kind=NodeKind.CLASS,
        )
