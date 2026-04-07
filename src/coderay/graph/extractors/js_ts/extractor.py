"""JavaScript/TypeScript CST -> graph facts."""

from __future__ import annotations

from coderay.graph.extractors.base import BaseGraphExtractor, HandlerMap
from coderay.graph.processors.js_ts.import_processor import JsTsImportProcessor
from coderay.graph.processors.js_ts.type_lookup import JsTsTypeLookup
from coderay.parsing.cst_kind import TraversalKind


class JsTsGraphExtractor(BaseGraphExtractor):
    """Lower JS/TS tree-sitter CST to graph facts."""

    def _build_handlers(self) -> HandlerMap:
        type_lookup = JsTsTypeLookup(self._session, self, self._find_class_node)
        callee = self._make_callee()
        return {
            TraversalKind.IMPORT: JsTsImportProcessor(self._session, self),
            TraversalKind.FUNCTION: self._make_function_def(),
            TraversalKind.CLASS: self._make_class_def(),
            TraversalKind.CALL: self._make_call(callee, type_lookup),
            TraversalKind.ASSIGNMENT: self._make_assignment(type_lookup),
        }
