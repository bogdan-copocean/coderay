"""Python CST → facts."""

from __future__ import annotations

from typing import Any

from coderay.graph.facts import Fact, ImportsEdge, ModuleInfo
from coderay.graph.file_context import FileContext
from coderay.graph.plugins.lowering_common import CallFactMixin
from coderay.graph.plugins.python.assignment_mixin import PythonAssignmentMixin
from coderay.graph.plugins.python.definition_mixin import PythonDefinitionMixin
from coderay.graph.plugins.python.descriptor import (
    PYTHON_GRAPH_DESCRIPTOR,
    PythonGraphDescriptor,
)
from coderay.graph.plugins.python.import_handler import PythonImportHandler
from coderay.graph.plugins.python.type_resolution_mixin import PythonTypeResolutionMixin
from coderay.parsing.base import BaseTreeSitterParser, ParserContext
from coderay.parsing.cst_kind import TraversalKind, classify_node

TSNode = Any


class PythonImportMixin:
    """Dispatch imports to PythonImportHandler."""

    def _handle_import(
        self, node: TSNode, *, scope_stack: list[str] | None = None
    ) -> None:
        """Create IMPORTS facts and register names in FileContext."""
        PythonImportHandler().handle(node, self, scope_stack=scope_stack or [])


class PythonGraphExtractor(
    PythonImportMixin,
    PythonTypeResolutionMixin,
    PythonDefinitionMixin,
    PythonAssignmentMixin,
    CallFactMixin,
    BaseTreeSitterParser,
):
    """Lower Python tree-sitter CST to graph facts."""

    def __init__(
        self,
        context: ParserContext,
        *,
        excluded_modules: frozenset[str],
        module_index: dict[str, str] | None = None,
        descriptor: PythonGraphDescriptor | None = None,
    ) -> None:
        super().__init__(context)
        self._desc = descriptor or PYTHON_GRAPH_DESCRIPTOR
        self._excluded_modules = excluded_modules
        self._module_id: str = context.file_path
        self._facts: list[Fact] = []
        self._module_index = module_index or {}
        self._file_ctx = FileContext(module_index=self._module_index)

    def _add_import_edge(self, source: str, target: str) -> None:
        self._facts.append(ImportsEdge(source_id=source, target=target))

    def extract_facts_list(self) -> list[Fact]:
        """Parse and return all facts for this file."""
        tree = self.get_tree()
        self._facts.append(
            ModuleInfo(
                file_path=self.file_path,
                end_line=tree.root_node.end_point[0] + 1,
            )
        )
        self._dfs(tree.root_node, scope_stack=[])
        return self._facts

    def _dfs(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Walk the CST."""
        ntype = node.type
        cfg = self._ctx.lang_cfg
        kind = classify_node(ntype, cfg)

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
        elif kind == TraversalKind.DECORATOR:
            self._handle_decorator(node, scope_stack=scope_stack)
        elif kind == TraversalKind.ASSIGNMENT:
            self._handle_assignment(node, scope_stack=scope_stack)
        elif kind == TraversalKind.WITH:
            self._handle_with_statement(node, scope_stack=scope_stack)

        for child in node.children:
            self._dfs(child, scope_stack=scope_stack)
