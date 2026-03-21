"""Python-only definition lowering (typed params, @property)."""

from __future__ import annotations

from typing import Any

from coderay.graph.plugins.lowering_common.definitions import DefinitionFactMixin

TSNode = Any


class PythonDefinitionMixin(DefinitionFactMixin):
    """Register typed parameters and @property return types on FileContext."""

    def _after_function_definition_registered(
        self, node: TSNode, *, scope_stack: list[str]
    ) -> None:
        """Apply typed-parameter and @property registration after symbol facts."""
        for param_name, type_refs in self._get_typed_parameters(node):
            if len(type_refs) == 1:
                self._file_ctx.register_instance(param_name, type_refs[0])
            else:
                self._file_ctx.register_instance_union(param_name, type_refs)

        if self._is_property(node) and scope_stack:
            name = self.identifier_from_node(node)
            if not name:
                return
            class_qualified = ".".join(scope_stack)
            return_type = self._get_return_type_from_func_node(node)
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
