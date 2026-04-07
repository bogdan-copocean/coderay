"""Shared graph extractor: DFS traversal with handler map dispatch."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from coderay.graph.facts import Fact, ModuleInfo
from coderay.graph.file_context import FileContext
from coderay.graph.lowering.session import LoweringSession
from coderay.graph.processors.node_processor import NodeProcessor
from coderay.parsing.base import BaseTreeSitterParser, ParserContext, TSNode
from coderay.parsing.cst_kind import TraversalKind, classify_node


@dataclass
class Handler:
    """Wraps a processor with traversal intent.

    order="pre"  — handle, then DFS recurses into children (default).
    order="post" — DFS recurses into children first, then handle.
    pushes_scope — handler.handle() returns a scope name; DFS recurses
                   under that name instead of the current scope_stack.
                   Implies no further recursion after the call (processor
                   owns the body implicitly via the scope push).
    """

    processor: NodeProcessor
    order: Literal["pre", "post"] = "pre"
    pushes_scope: bool = field(default=False)


# Languages declare only the kinds they handle; absent kinds recurse silently.
HandlerMap = dict[TraversalKind, Handler]


class BaseGraphExtractor(ABC):
    """Lower a source file's CST to graph facts; subclass per language.

    Only requirement: implement _build_handlers().
    """

    def __init__(
        self,
        context: ParserContext,
        *,
        module_index: dict[str, str] | None = None,
    ) -> None:
        self._parser = BaseTreeSitterParser(context)
        self._module_id: str = context.file_path
        self._module_index = module_index or {}
        self._session = LoweringSession(
            facts=set(),
            file_ctx=self._build_file_context(),
            module_id=self._module_id,
        )
        self._handlers: HandlerMap = self._build_handlers()

    @abstractmethod
    def _build_handlers(self) -> HandlerMap:
        """Declare which node kinds this language handles and how."""

    def _build_file_context(self) -> FileContext:
        return FileContext(module_index=self._module_index)

    @property
    def _file_ctx(self) -> FileContext:
        return self._session.file_ctx

    @property
    def _facts(self) -> set[Fact]:
        return self._session.facts

    def extract_facts_list(self) -> set[Fact]:
        tree = self._parser.get_tree()
        self._session.facts.add(
            ModuleInfo(
                file_path=self._parser.file_path,
                end_line=tree.root_node.end_point[0] + 1,
            )
        )
        self._dfs(tree.root_node, scope_stack=[])
        return self._session.facts

    def _dfs(self, node: TSNode, *, scope_stack: list[str]) -> None:
        kind = classify_node(node.type, self._parser.lang_cfg)
        entry = self._handlers.get(kind)

        if entry is None:
            for child in node.children:
                self._dfs(child, scope_stack=scope_stack)
            return

        if entry.order == "post":
            for child in node.children:
                self._dfs(child, scope_stack=scope_stack)
            entry.processor.handle(node, scope_stack=scope_stack)
            return

        # pre-order
        scope_name = entry.processor.handle(node, scope_stack=scope_stack)
        if entry.pushes_scope:
            # Processor registered a new scope — recurse under it.
            if scope_name:
                new_scope = [*scope_stack, scope_name]
                for child in node.children:
                    self._dfs(child, scope_stack=new_scope)
        else:
            for child in node.children:
                self._dfs(child, scope_stack=scope_stack)

    def _find_class_node(self, class_name: str) -> TSNode | None:
        """Find a class definition node by name (recursive tree search)."""
        tree = self._parser.get_tree()
        class_types = self._parser.lang_cfg.cst.class_scope_types

        def _search(n: TSNode) -> TSNode | None:
            if n.type in class_types:
                name_node = n.child_by_field_name("name") or (
                    n.named_children[0] if n.named_children else None
                )
                if name_node and self._parser.node_text(name_node) == class_name:
                    return n
            for c in n.children:
                found = _search(c)
                if found:
                    return found
            return None

        return _search(tree.root_node)
