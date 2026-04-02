"""Shared graph extractor: init, DFS, import dispatch, common helpers."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from coderay.graph.facts import Fact, ImportsEdge, ModuleInfo
from coderay.graph.file_context import FileContext
from coderay.graph.plugins.base.handlers.assignments import AssignmentMixin
from coderay.graph.plugins.base.handlers.calls import CallMixin
from coderay.graph.plugins.base.handlers.definitions import DefinitionMixin
from coderay.graph.plugins.base.handlers.type_resolution import TypeResolutionMixin
from coderay.parsing.base import BaseTreeSitterParser, ParserContext, TSNode
from coderay.parsing.cst_kind import TraversalKind, classify_node


@runtime_checkable
class ImportHandler(Protocol):
    """Contract for language-specific import handlers."""

    def handle(
        self, node: TSNode, extractor: Any, *, scope_stack: list[str]
    ) -> None: ...


class BaseGraphExtractor(
    TypeResolutionMixin,
    DefinitionMixin,
    AssignmentMixin,
    CallMixin,
    BaseTreeSitterParser,
):
    """Lower tree-sitter CST to graph facts; subclass per language."""

    _import_handler: ImportHandler | None = None

    def __init__(
        self,
        context: ParserContext,
        *,
        module_index: dict[str, str] | None = None,
    ) -> None:
        """Initialize with language context and graph extraction state."""
        super().__init__(context)
        self._module_id: str = context.file_path
        self._facts: set[Fact] = set()
        self._module_index = module_index or {}
        self._file_ctx = FileContext(module_index=self._module_index)
        # Cache for chain resolution — avoids rebuilding every call
        self._supported_extensions: set[str] = _get_supported_extensions_cached()

    def _add_import_edge(self, source: str, target: str) -> None:
        """Append an IMPORTS fact."""
        self._facts.add(ImportsEdge(source_id=source, target=target))

    def extract_facts_list(self) -> set[Fact]:
        """Parse file and return all extracted facts."""
        tree = self.get_tree()
        self._facts.add(
            ModuleInfo(
                file_path=self.file_path,
                end_line=tree.root_node.end_point[0] + 1,
            )
        )
        self._dfs(tree.root_node, scope_stack=[])
        return self._facts

    def _dfs(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Walk the CST, dispatching to handler methods by node kind.

        FUNCTION and CLASS handlers recurse into their own body (with updated
        scope_stack), so we return early to avoid double-visiting children.
        DECORATED_DEFINITION recurses first (to register the inner def/class),
        then emits decorator call edges — also returns early.
        All other handlers process the current node; children are visited below.
        """
        kind = classify_node(node.type, self._ctx.lang_cfg)

        if kind == TraversalKind.IMPORT:
            self._handle_import(node, scope_stack=scope_stack)
        elif kind == TraversalKind.FUNCTION:
            self._handle_function_def(node, scope_stack=scope_stack)
            return
        elif kind == TraversalKind.CLASS:
            self._handle_class_def(node, scope_stack=scope_stack)
            return
        elif kind == TraversalKind.CALL:
            self._handle_call(node, scope_stack=scope_stack)
        elif kind == TraversalKind.DECORATED_DEFINITION:
            for child in node.children:
                self._dfs(child, scope_stack=scope_stack)
            self._handle_decorator(node, scope_stack=scope_stack)
            return
        elif kind == TraversalKind.ASSIGNMENT:
            self._handle_assignment(node, scope_stack=scope_stack)
        elif kind == TraversalKind.WITH:
            self._handle_with_statement(node, scope_stack=scope_stack)

        for child in node.children:
            self._dfs(child, scope_stack=scope_stack)

    def _handle_import(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Dispatch to language-specific import handler."""
        if self._import_handler is not None:
            self._import_handler.handle(node, self, scope_stack=scope_stack)

    # ------------------------------------------------------------------
    # Shared CST helper
    # ------------------------------------------------------------------

    def _find_class_node(self, class_name: str) -> TSNode | None:
        """Find a class definition node by name (recursive tree search)."""
        tree = self.get_tree()
        class_types = self._ctx.lang_cfg.cst.class_scope_types

        def _search(n: TSNode) -> TSNode | None:
            if n.type in class_types:
                name_node = n.child_by_field_name("name") or (
                    n.named_children[0] if n.named_children else None
                )
                if name_node and self.node_text(name_node) == class_name:
                    return n
            for c in n.children:
                found = _search(c)
                if found:
                    return found
            return None

        return _search(tree.root_node)


_SUPPORTED_EXT_CACHE: set[str] | None = None


def _get_supported_extensions_cached() -> set[str]:
    """Return cached supported extensions set."""
    global _SUPPORTED_EXT_CACHE
    if _SUPPORTED_EXT_CACHE is None:
        from coderay.parsing.languages import get_supported_extensions

        _SUPPORTED_EXT_CACHE = get_supported_extensions()
    return _SUPPORTED_EXT_CACHE
