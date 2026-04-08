"""JavaScript/TypeScript CST -> graph facts."""

from __future__ import annotations

from coderay.core.models import NodeKind
from coderay.graph.extractors.base import (
    BaseGraphExtractor,
    BindingHandler,
    BindingHandlerMap,
    FactHandler,
    FactHandlerMap,
)
from coderay.graph.handlers.assignment_binder import AssignmentBinder
from coderay.graph.handlers.call_emitter import CallEmitter
from coderay.graph.handlers.definition_binder import DefinitionBinder
from coderay.graph.handlers.definition_emitter import DefinitionEmitter
from coderay.graph.handlers.js_ts.import_binder import JsTsImportBinder
from coderay.graph.handlers.js_ts.import_emitter import JsTsImportEmitter
from coderay.graph.lowering.callee_resolver import CalleeResolver
from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.cst_kind import TraversalKind


class JsTsGraphExtractor(BaseGraphExtractor):
    """Lower JS/TS tree-sitter CST to graph facts."""

    def _build_binding_handlers(self, bindings: FileNameBindings) -> BindingHandlerMap:
        module_id = self._module_id

        return {
            TraversalKind.IMPORT: BindingHandler(JsTsImportBinder()),
            TraversalKind.FUNCTION: BindingHandler(
                DefinitionBinder(module_id, NodeKind.FUNCTION)
            ),
            TraversalKind.CLASS: BindingHandler(
                DefinitionBinder(module_id, NodeKind.CLASS)
            ),
            TraversalKind.ASSIGNMENT: BindingHandler(AssignmentBinder()),
        }

    def _build_fact_handlers(self, resolver: CalleeResolver) -> FactHandlerMap:
        module_id = self._module_id

        return {
            TraversalKind.IMPORT: FactHandler(JsTsImportEmitter()),
            TraversalKind.FUNCTION: FactHandler(
                DefinitionEmitter(module_id, NodeKind.FUNCTION)
            ),
            TraversalKind.CLASS: FactHandler(
                DefinitionEmitter(module_id, NodeKind.CLASS)
            ),
            TraversalKind.CALL: FactHandler(CallEmitter(resolver)),
        }
