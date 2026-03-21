"""JS/TS-specific type resolution (arrow functions, class methods)."""

from __future__ import annotations

from typing import Any

from coderay.graph.plugins.lowering_common.type_resolution import TypeResolutionCoreMixin

TSNode = Any


class JsTsTypeResolutionMixin(TypeResolutionCoreMixin):
    """Find methods and functions in JS/TS CST."""

    def _find_method_in_class(self, class_name: str, method_name: str) -> TSNode | None:
        """Find method_definition in class body."""
        tree = self.get_tree()
        class_types = (
            self._ctx.lang_cfg.class_scope_types + self._desc.extra_class_scope_types
        )
        body_types = self._desc.class_body_types

        def find_class(n: TSNode) -> TSNode | None:
            if n.type in class_types:
                name_node = n.child_by_field_name("name") or (
                    n.named_children[0] if n.named_children else None
                )
                if name_node and self.node_text(name_node) == class_name:
                    return n
            for c in n.children:
                found = find_class(c)
                if found:
                    return found
            return None

        class_node = find_class(tree.root_node)
        if not class_node:
            return None
        for child in class_node.children:
            if child.type not in body_types:
                continue
            for stmt in child.children:
                if stmt.type != "method_definition":
                    continue
                name_node = stmt.child_by_field_name("name")
                if name_node and self.node_text(name_node) == method_name:
                    return stmt
        return None

    def _find_top_level_function(self, func_name: str) -> TSNode | None:
        """Find top-level function by name."""

        def search(n: TSNode) -> TSNode | None:
            if n.type in ("function_declaration", "function_definition"):
                name_node = n.child_by_field_name("name")
                if name_node and self.node_text(name_node) == func_name:
                    return n
            if n.type == "variable_declarator":
                name_node = n.child_by_field_name("name")
                if name_node and self.node_text(name_node) == func_name:
                    value = n.child_by_field_name("value")
                    if value and value.type == "arrow_function":
                        return value
            for c in n.children:
                found = search(c)
                if found:
                    return found
            return None

        return search(self.get_tree().root_node)
