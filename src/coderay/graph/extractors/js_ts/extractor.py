"""JavaScript/TypeScript CST -> graph facts."""

from __future__ import annotations

from coderay.graph.extractors.base import BaseGraphExtractor, Handler, HandlerMap
from coderay.graph.processors.assignment import AssignmentProcessor
from coderay.graph.processors.call import CallProcessor
from coderay.graph.processors.callee_resolution import CalleeResolution
from coderay.graph.processors.definition import (
    ClassDefinitionProcessor,
    FunctionDefinitionProcessor,
)
from coderay.graph.processors.js_ts.import_processor import JsTsImportProcessor
from coderay.graph.processors.js_ts.type_lookup import JsTsTypeLookup
from coderay.parsing.cst_kind import TraversalKind


class JsTsGraphExtractor(BaseGraphExtractor):
    """Lower JS/TS tree-sitter CST to graph facts."""

    def _build_handlers(self) -> HandlerMap:
        parser = self._parser
        session = self._session
        type_lookup = JsTsTypeLookup(session, parser, self._find_class_node)
        callee = CalleeResolution(session, parser, self._find_class_node)

        return {
            TraversalKind.IMPORT: Handler(JsTsImportProcessor(session, parser)),
            TraversalKind.FUNCTION: Handler(
                FunctionDefinitionProcessor(session, parser, self._dfs)
            ),
            TraversalKind.CLASS: Handler(
                ClassDefinitionProcessor(session, parser, self._dfs)
            ),
            TraversalKind.CALL: Handler(
                CallProcessor(session, parser, type_lookup, callee)
            ),
            TraversalKind.ASSIGNMENT: Handler(
                AssignmentProcessor(session, parser, type_lookup)
            ),
        }
