"""Shared graph extractor: init, DFS, import dispatch, composition-based handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from coderay.graph.facts import Fact, ModuleInfo
from coderay.graph.file_context import FileContext
from coderay.graph.lowering.session import LoweringSession
from coderay.graph.processors.assignment import AssignmentProcessor
from coderay.graph.processors.call import CallProcessor
from coderay.graph.processors.callee_resolution import CalleeResolution
from coderay.graph.processors.decorator import DecoratorProcessor
from coderay.graph.processors.definition import (
    ClassDefinitionProcessor,
    FunctionDefinitionProcessor,
)
from coderay.graph.processors.imports import ImportProcessor
from coderay.graph.processors.node_processor import NodeProcessor
from coderay.graph.processors.scope import caller_id_for_scope
from coderay.graph.processors.type_lookup import TypeLookup
from coderay.graph.processors.with_statement import WithStatementProcessor
from coderay.parsing.base import BaseTreeSitterParser, ParserContext, TSNode
from coderay.parsing.cst_kind import TraversalKind, classify_node


class BaseGraphExtractor(BaseTreeSitterParser, ABC):
    """Lower tree-sitter CST to graph facts; subclass per language."""

    _import_processor_cls: type[ImportProcessor] | None = None
    _assignment_processor_cls: type[AssignmentProcessor] = AssignmentProcessor
    _with_processor_cls: type[WithStatementProcessor] = WithStatementProcessor

    def __init__(
        self,
        context: ParserContext,
        *,
        module_index: dict[str, str] | None = None,
    ) -> None:
        """Initialize with language context and graph extraction state."""
        super().__init__(context)
        # Caller id for module-scope (no function/class in scope_stack).
        self._module_id: str = context.file_path
        self._module_index = module_index or {}
        self._session = LoweringSession(
            facts=set(),
            file_ctx=FileContext(module_index=self._module_index),
            module_id=self._module_id,
        )
        self._supported_extensions: set[str] = _get_supported_extensions_cached()
        self._type_lookup = self._build_type_lookup()

        # After function symbol is registered (Python: params / @property).
        def _after_fn(n: TSNode, s: list[str]) -> None:
            self._after_function_definition_registered(n, scope_stack=s)

        def _walk(n: TSNode, s: list[str]) -> None:
            self._dfs(n, scope_stack=s)

        self._function_def_proc: NodeProcessor = FunctionDefinitionProcessor(
            self._session,
            self,
            _walk,
            after_function_registered=_after_fn,
        )
        self._class_def_proc: NodeProcessor = ClassDefinitionProcessor(
            self._session,
            self,
            _walk,
        )
        self._callee = CalleeResolution(
            self._session,
            self,
            self._find_class_node,
            self._supported_extensions,
        )
        self._call_proc: NodeProcessor = CallProcessor(
            self._session,
            self,
            self._type_lookup,
            self._callee,
        )
        self._decorator_proc: NodeProcessor = DecoratorProcessor(
            self._session,
            self,
            self._callee,
        )
        self._assign_proc: NodeProcessor = self._assignment_processor_cls(
            self._session, self, self._type_lookup
        )
        self._with_proc: NodeProcessor = self._with_processor_cls(
            self._session, self, self._type_lookup
        )
        self._import_proc: ImportProcessor | None = (
            self._import_processor_cls(self._session, self)
            if self._import_processor_cls is not None
            else None
        )

    @abstractmethod
    def _build_type_lookup(self) -> TypeLookup:
        """Language-specific type lookup (function resolution in CST)."""

    @property
    def _facts(self) -> set[Fact]:
        return self._session.facts

    @property
    def _file_ctx(self) -> FileContext:
        return self._session.file_ctx

    def _after_function_definition_registered(
        self, node: TSNode, *, scope_stack: list[str]
    ) -> None:
        del node, scope_stack

    def _caller_id_from_scope(self, scope_stack: list[str]) -> str:
        return caller_id_for_scope(self._session, self, scope_stack)

    def extract_facts_list(self) -> set[Fact]:
        """Parse file and return all extracted facts."""
        tree = self.get_tree()
        self._session.facts.add(
            ModuleInfo(
                file_path=self.file_path,
                end_line=tree.root_node.end_point[0] + 1,
            )
        )
        self._dfs(tree.root_node, scope_stack=[])
        return self._session.facts

    def _dfs(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Walk the CST; function/class/decorated branches return early."""
        kind = classify_node(node.type, self._ctx.lang_cfg)

        if kind == TraversalKind.IMPORT:
            self._handle_import(node, scope_stack=scope_stack)
        elif kind == TraversalKind.FUNCTION:
            self._function_def_proc.handle(node, scope_stack=scope_stack)
            return
        elif kind == TraversalKind.CLASS:
            self._class_def_proc.handle(node, scope_stack=scope_stack)
            return
        elif kind == TraversalKind.CALL:
            self._call_proc.handle(node, scope_stack=scope_stack)
        elif kind == TraversalKind.DECORATED_DEFINITION:
            for child in node.children:
                self._dfs(child, scope_stack=scope_stack)
            self._decorator_proc.handle(node, scope_stack=scope_stack)
            return
        elif kind == TraversalKind.ASSIGNMENT:
            self._assign_proc.handle(node, scope_stack=scope_stack)
        elif kind == TraversalKind.WITH:
            self._with_proc.handle(node, scope_stack=scope_stack)

        # Nested nodes (e.g. calls inside statements) not consumed above.
        for child in node.children:
            self._dfs(child, scope_stack=scope_stack)

    def _handle_import(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Dispatch to language-specific import processor."""
        if self._import_proc is not None:
            self._import_proc.handle(node, scope_stack=scope_stack)

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
