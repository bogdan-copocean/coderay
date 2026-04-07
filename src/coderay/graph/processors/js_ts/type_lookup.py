"""JS/TS: class methods and top-level functions for typing."""

from __future__ import annotations

from coderay.graph.processors.type_lookup import _TypeLookupCore
from coderay.parsing.base import TSNode


class JsTsTypeLookup(_TypeLookupCore):
    """JS/TS method_definition / function_declaration / arrow lookup."""

    def find_method_in_class_body(
        self, class_node: TSNode, method_name: str
    ) -> TSNode | None:
        body_types = self._syntax.lang_cfg.cst.class_body_types
        for child in class_node.children:
            if child.type not in body_types:
                continue
            for stmt in child.children:
                if stmt.type != "method_definition":
                    continue
                name_node = stmt.child_by_field_name("name")
                if name_node and self._syntax.node_text(name_node) == method_name:
                    return stmt
        return None

    def find_top_level_function(self, func_name: str) -> TSNode | None:
        def search(n: TSNode) -> TSNode | None:
            if n.type in ("function_declaration", "function_definition"):
                name_node = n.child_by_field_name("name")
                if name_node and self._syntax.node_text(name_node) == func_name:
                    return n
            if n.type == "variable_declarator":
                name_node = n.child_by_field_name("name")
                if name_node and self._syntax.node_text(name_node) == func_name:
                    value = n.child_by_field_name("value")
                    if value and value.type == "arrow_function":
                        return value
            for c in n.children:
                found = search(c)
                if found:
                    return found
            return None

        return search(self._syntax.get_tree().root_node)
