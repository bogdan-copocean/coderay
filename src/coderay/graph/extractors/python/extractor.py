"""Python CST -> graph facts."""

from __future__ import annotations

from coderay.graph.extractors.base import BaseGraphExtractor, Handler, HandlerMap
from coderay.graph.processors.assignment import AssignmentProcessor
from coderay.graph.processors.call import CallProcessor
from coderay.graph.processors.callee_resolution import CalleeResolution
from coderay.graph.processors.decorator import DecoratorProcessor
from coderay.graph.processors.definition import (
    ClassDefinitionProcessor,
    FunctionDefinitionProcessor,
)
from coderay.graph.processors.python.assignment_processor import (
    PythonAssignmentProcessor,
)
from coderay.graph.processors.python.import_processor import PythonImportProcessor
from coderay.graph.processors.python.type_lookup import PythonTypeLookup
from coderay.graph.processors.python.with_statement_processor import (
    PythonWithStatementProcessor,
)
from coderay.parsing.base import TSNode
from coderay.parsing.cst_kind import TraversalKind


class PythonGraphExtractor(BaseGraphExtractor):
    """Lower Python tree-sitter CST to graph facts."""

    def _build_handlers(self) -> HandlerMap:
        parser = self._parser
        session = self._session
        type_lookup = PythonTypeLookup(session, parser, self._find_class_node)
        callee = CalleeResolution(session, parser, self._find_class_node)

        return {
            TraversalKind.IMPORT: Handler(PythonImportProcessor(session, parser)),
            TraversalKind.FUNCTION: Handler(
                PythonFunctionDefinitionProcessor(
                    session, parser, type_lookup, self._file_ctx
                ),
                pushes_scope=True,
            ),
            TraversalKind.CLASS: Handler(
                ClassDefinitionProcessor(session, parser),
                pushes_scope=True,
            ),
            TraversalKind.CALL: Handler(
                CallProcessor(session, parser, type_lookup, callee)
            ),
            TraversalKind.DECORATED_DEFINITION: Handler(
                DecoratorProcessor(session, parser, callee), order="post"
            ),
            TraversalKind.ASSIGNMENT: Handler(
                PythonAssignmentProcessor(session, parser, type_lookup)
            ),
            TraversalKind.WITH: Handler(
                PythonWithStatementProcessor(session, parser, type_lookup)
            ),
        }


class PythonFunctionDefinitionProcessor(FunctionDefinitionProcessor):
    """FunctionDefinitionProcessor + typed param and @property registration."""

    def __init__(self, session, parser, type_lookup, file_ctx) -> None:
        super().__init__(session, parser)
        self._type_lookup = type_lookup
        self._file_ctx = file_ctx

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        # Register typed params and @property attrs before DFS recurses into body.
        for param_name, type_refs in self._type_lookup.get_typed_parameters(node):
            if len(type_refs) == 1:
                self._file_ctx.register_instance(param_name, type_refs[0])
            else:
                self._file_ctx.register_instance_union(param_name, type_refs)

        if scope_stack and _is_property(self._parser, node):
            name = self._parser.identifier_from_node(node)
            return_type = self._type_lookup.get_return_type_from_func_node(node)
            if name and return_type:
                self._file_ctx.register_class_attribute(
                    ".".join(scope_stack), name, return_type
                )

        return super().handle(node, scope_stack=scope_stack)


def _is_property(parser, func_node: TSNode) -> bool:
    parent = func_node.parent
    if parent is None or parent.type != "decorated_definition":
        return False
    return any(
        parser.node_text(child).strip().endswith("property")
        for child in parent.children
        if child.type == "decorator"
    )
