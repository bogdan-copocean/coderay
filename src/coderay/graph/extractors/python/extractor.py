"""Python CST -> graph facts."""

from __future__ import annotations

from coderay.graph.extractors.base import BaseGraphExtractor
from coderay.graph.processors.python.assignment_processor import (
    PythonAssignmentProcessor,
)
from coderay.graph.processors.python.import_processor import PythonImportProcessor
from coderay.graph.processors.python.type_lookup import PythonTypeLookup
from coderay.graph.processors.python.with_statement_processor import (
    PythonWithStatementProcessor,
)
from coderay.graph.processors.type_lookup import TypeLookup
from coderay.parsing.base import TSNode


class PythonGraphExtractor(BaseGraphExtractor):
    """Lower Python tree-sitter CST to graph facts."""

    _assignment_processor_cls = PythonAssignmentProcessor
    _with_processor_cls = PythonWithStatementProcessor
    _import_processor_cls = PythonImportProcessor

    def _build_type_lookup(self) -> TypeLookup:
        return PythonTypeLookup(self._session, self, self._find_class_node)

    def _after_function_definition_registered(
        self, node: TSNode, *, scope_stack: list[str]
    ) -> None:
        # def __init__(self, repo: UserRepository):  ->  register repo as instance
        # @property \n def name(self) -> str:  ->  register class attribute
        for param_name, type_refs in self._type_lookup.get_typed_parameters(node):
            if len(type_refs) == 1:
                self._file_ctx.register_instance(param_name, type_refs[0])
            else:
                self._file_ctx.register_instance_union(param_name, type_refs)

        if self._is_property(node) and scope_stack:
            name = self.identifier_from_node(node)
            if not name:
                return
            class_qualified = ".".join(scope_stack)
            return_type = self._type_lookup.get_return_type_from_func_node(node)
            if return_type:
                self._file_ctx.register_class_attribute(
                    class_qualified, name, return_type
                )

    def _is_property(self, func_node: TSNode) -> bool:
        """Return True if function has @property decorator."""
        parent = func_node.parent
        if parent is None or parent.type != "decorated_definition":
            return False
        for child in parent.children:
            if child.type == "decorator":
                text = self.node_text(child).strip()
                if text.endswith("property"):
                    return True
        return False
