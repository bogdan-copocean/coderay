"""Python: locate methods in class bodies and top-level functions for typing."""

from __future__ import annotations

from coderay.graph.processors.type_lookup import _TypeLookupCore
from coderay.parsing.base import TSNode


class PythonTypeLookup(_TypeLookupCore):
    """Python class-body and module-scope function lookup."""

    def find_method_in_class_body(
        self, class_node: TSNode, method_name: str
    ) -> TSNode | None:
        body_types = self._syntax._ctx.lang_cfg.cst.class_body_types
        for child in class_node.children:
            if child.type not in body_types:
                continue
            for stmt in child.children:
                fn = self._unwrap_decorated(stmt)
                if fn is None:
                    continue
                name_node = fn.child_by_field_name("name")
                if name_node and self._syntax.node_text(name_node) == method_name:
                    return fn
        return None

    def find_top_level_function(self, func_name: str) -> TSNode | None:
        def search(n: TSNode) -> TSNode | None:
            if n.type == "function_definition":
                name_node = n.child_by_field_name("name")
                if name_node and self._syntax.node_text(name_node) == func_name:
                    return n
            for c in n.children:
                found = search(c)
                if found:
                    return found
            return None

        return search(self._syntax.get_tree().root_node)

    def _unwrap_decorated(self, stmt: TSNode) -> TSNode | None:
        """Return function_definition, including from decorated_definition."""
        if stmt.type == "function_definition":
            return stmt
        if stmt.type == "decorated_definition":
            for c in stmt.children:
                if c.type == "function_definition":
                    return c
        return None
