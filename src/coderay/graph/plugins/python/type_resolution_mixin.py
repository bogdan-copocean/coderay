"""Python-specific type resolution (decorators, tuple[...], top-level def)."""

from __future__ import annotations

from typing import Any

from coderay.graph.plugins.lowering_common.type_resolution import (
    TypeResolutionCoreMixin,
)

TSNode = Any


class PythonTypeResolutionMixin(TypeResolutionCoreMixin):
    """Find methods and functions in Python CST; extract tuple[...] type args."""

    def _find_method_in_class(self, class_name: str, method_name: str) -> TSNode | None:
        """Find method definition in class."""
        tree = self.get_tree()
        dispatch = self._ctx.lang_cfg.cst
        class_types = dispatch.class_scope_types
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
                fn = self._unwrap_decorated(stmt)
                if fn is None:
                    continue
                fn_name = self.node_text(fn.child_by_field_name("name"))
                if fn_name == method_name:
                    return fn
        return None

    def _find_top_level_function(self, func_name: str) -> TSNode | None:
        """Find top-level function by name."""

        def search(n: TSNode) -> TSNode | None:
            if n.type == "function_definition":
                name_node = n.child_by_field_name("name")
                if name_node and self.node_text(name_node) == func_name:
                    return n
            for c in n.children:
                found = search(c)
                if found:
                    return found
            return None

        return search(self.get_tree().root_node)

    def _unwrap_decorated(self, stmt: TSNode) -> TSNode | None:
        """Return inner function_definition from decorated_definition."""
        if stmt.type == "function_definition":
            return stmt
        if stmt.type == "decorated_definition":
            for c in stmt.children:
                if c.type == "function_definition":
                    return c
        return None

    def _extract_tuple_type_args(self, type_node: TSNode) -> list[str]:
        """Extract type args from tuple[X, Y, ...] in the type CST subtree."""
        if type_node.type == "type" and type_node.named_children:
            type_node = type_node.named_children[0]
        if type_node.type != "generic_type":
            return []
        children = type_node.named_children
        if len(children) < 2:
            return []
        base_name = self.node_text(children[0])
        if base_name.lower() != "tuple":
            return []
        type_param_node = children[1]
        result: list[str] = []
        for type_child in type_param_node.named_children:
            if type_child.type == "type":
                refs = self._resolve_type_texts(self.node_text(type_child))
                result.extend(refs)
        return result
