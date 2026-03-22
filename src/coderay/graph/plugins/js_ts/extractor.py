"""JavaScript/TypeScript CST → facts."""

from __future__ import annotations

from typing import Any

from coderay.graph.facts import Fact, ImportsEdge, ModuleInfo
from coderay.graph.file_context import FileContext
from coderay.graph.plugins.js_ts.descriptor import (
    JS_TS_GRAPH_DESCRIPTOR,
    JsTsGraphDescriptor,
)
from coderay.graph.plugins.js_ts.import_handler import JsTsImportHandler
from coderay.graph.plugins.js_ts.type_resolution_mixin import JsTsTypeResolutionMixin
from coderay.graph.plugins.lowering_common import (
    AssignmentCoreMixin,
    CallFactMixin,
    DefinitionFactMixin,
)
from coderay.parsing.base import BaseTreeSitterParser, ParserContext
from coderay.parsing.cst_kind import TraversalKind, classify_node

TSNode = Any


class JsTsImportMixin:
    """Dispatch imports to JsTsImportHandler."""

    def _handle_import(
        self, node: TSNode, *, scope_stack: list[str] | None = None
    ) -> None:
        JsTsImportHandler().handle(node, self, scope_stack=scope_stack or [])


class JsTsGraphExtractor(
    JsTsImportMixin,
    JsTsTypeResolutionMixin,
    DefinitionFactMixin,
    AssignmentCoreMixin,
    CallFactMixin,
    BaseTreeSitterParser,
):
    """Lower JS/TS tree-sitter CST to graph facts."""

    def __init__(
        self,
        context: ParserContext,
        *,
        excluded_modules: frozenset[str],
        module_index: dict[str, str] | None = None,
        descriptor: JsTsGraphDescriptor | None = None,
    ) -> None:
        super().__init__(context)
        self._desc = descriptor or JS_TS_GRAPH_DESCRIPTOR
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
        elif kind == TraversalKind.ASSIGNMENT:
            self._handle_assignment(node, scope_stack=scope_stack)

        for child in node.children:
            self._dfs(child, scope_stack=scope_stack)
