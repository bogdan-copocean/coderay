"""Python CST -> graph facts."""

from __future__ import annotations

from coderay.core.models import NodeKind
from coderay.graph.extractors.base import (
    BaseGraphExtractor,
    BindingHandler,
    BindingHandlerMap,
    FactHandler,
    FactHandlerMap,
)
from coderay.graph.handlers.call_emitter import CallEmitter
from coderay.graph.handlers.decorator_emitter import DecoratorEmitter
from coderay.graph.handlers.definition_binder import DefinitionBinder
from coderay.graph.handlers.definition_emitter import DefinitionEmitter
from coderay.graph.handlers.python.assignment_binder import PythonAssignmentBinder
from coderay.graph.handlers.python.function_binder import PythonFunctionBinder
from coderay.graph.handlers.python.import_binder import PythonImportBinder
from coderay.graph.handlers.python.import_emitter import PythonImportEmitter
from coderay.graph.handlers.python.with_binder import PythonWithBinder
from coderay.graph.lowering.callee_strategy import CalleeStrategy
from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.cst_kind import TraversalKind


class PythonGraphExtractor(BaseGraphExtractor):
    """Lower Python tree-sitter CST to graph facts."""

    def _build_binding_handlers(self, bindings: FileNameBindings) -> BindingHandlerMap:
        module_id = self._module_id

        return {
            TraversalKind.IMPORT: BindingHandler(PythonImportBinder()),
            TraversalKind.FUNCTION: BindingHandler(PythonFunctionBinder(module_id)),
            TraversalKind.CLASS: BindingHandler(
                DefinitionBinder(module_id, NodeKind.CLASS)
            ),
            TraversalKind.ASSIGNMENT: BindingHandler(PythonAssignmentBinder()),
            TraversalKind.WITH: BindingHandler(PythonWithBinder()),
        }

    def _build_fact_handlers(self, resolver: CalleeStrategy) -> FactHandlerMap:
        module_id = self._module_id

        return {
            TraversalKind.IMPORT: FactHandler(PythonImportEmitter()),
            TraversalKind.FUNCTION: FactHandler(
                DefinitionEmitter(module_id, NodeKind.FUNCTION)
            ),
            TraversalKind.CLASS: FactHandler(
                DefinitionEmitter(module_id, NodeKind.CLASS)
            ),
            TraversalKind.CALL: FactHandler(CallEmitter(resolver)),
            TraversalKind.DECORATED_DEFINITION: FactHandler(
                DecoratorEmitter(resolver), order="post"
            ),
        }
