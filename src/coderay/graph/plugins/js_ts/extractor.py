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
from coderay.graph.plugins.mixins import (
    AssignmentFactMixin,
    CallFactMixin,
    DefinitionFactMixin,
    TypeResolutionFactMixin,
)
from coderay.parsing.base import BaseTreeSitterParser, ParserContext

TSNode = Any


class JsTsImportMixin:
    """Dispatch imports to JsTsImportHandler."""

    def _handle_import(
        self, node: TSNode, *, scope_stack: list[str] | None = None
    ) -> None:
        JsTsImportHandler().handle(node, self, scope_stack=scope_stack or [])


class JsTsGraphExtractor(
    JsTsImportMixin,
    TypeResolutionFactMixin,
    DefinitionFactMixin,
    AssignmentFactMixin,
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
        """Walk the AST."""
        ntype = node.type
        cfg = self._ctx.lang_cfg
        desc = self._desc

        if ntype in cfg.import_types:
            self._handle_import(node, scope_stack=scope_stack)
        elif ntype in cfg.function_scope_types:
            self._handle_function_def(node, scope_stack=scope_stack)
            return
        elif ntype in cfg.class_scope_types or ntype in desc.extra_class_scope_types:
            self._handle_class_def(node, scope_stack=scope_stack)
            return
        elif ntype in desc.call_types:
            self._handle_call(node, scope_stack=scope_stack)
        elif ntype in desc.decorator_types:
            self._handle_decorator(node, scope_stack=scope_stack)
        elif ntype in desc.assignment_types:
            self._handle_assignment(node, scope_stack=scope_stack)
        elif ntype in desc.with_types:
            self._handle_with_statement(node, scope_stack=scope_stack)

        for child in node.children:
            self._dfs(child, scope_stack=scope_stack)
