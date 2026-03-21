"""Class/function definition lowering (shared)."""

from __future__ import annotations

from typing import Any

from coderay.core.models import NodeKind
from coderay.graph._utils import _BASE_CLASS_NODE_TYPES
from coderay.graph.facts import InheritsEdge, SymbolDefinition

TSNode = Any


class DefinitionFactMixin:
    """Handle class/function definitions: symbols and INHERITS facts."""

    def _handle_function_def(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Record function symbol; recurse into body."""
        name = self.identifier_from_node(node)
        if not name:
            return

        qualified = ".".join([*scope_stack, name])
        definer = self._module_id
        if scope_stack:
            definer = f"{self.file_path}::{'.'.join(scope_stack)}"

        self._facts.append(
            SymbolDefinition(
                file_path=self.file_path,
                scope_stack=tuple(scope_stack),
                name=name,
                kind=NodeKind.FUNCTION,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                definer_id=definer,
            )
        )
        node_id = f"{self.file_path}::{qualified}"

        if not scope_stack:
            self._file_ctx.register_definition(name, node_id)
        else:
            self._file_ctx.register_definition(qualified, node_id)

        for param_name, type_refs in self._get_typed_parameters(node):
            if len(type_refs) == 1:
                self._file_ctx.register_instance(param_name, type_refs[0])
            else:
                self._file_ctx.register_instance_union(param_name, type_refs)

        if self._is_property(node) and scope_stack:
            class_qualified = ".".join(scope_stack)
            return_type = self._get_return_type_from_func_node(node)
            if return_type:
                self._file_ctx.register_class_attribute(
                    class_qualified, name, return_type
                )

        new_scope = [*scope_stack, name]
        for child in node.children:
            self._dfs(child, scope_stack=new_scope)

    def _is_property(self, func_node: TSNode) -> bool:
        """Return True if function has @property decorator."""
        if not self._desc.tracks_property_types:
            return False
        parent = func_node.parent
        if parent is None or parent.type != "decorated_definition":
            return False
        for child in parent.children:
            if child.type == "decorator":
                text = self.node_text(child).strip()
                if text.endswith("property"):
                    return True
        return False

    def _handle_class_def(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Record class symbol and base INHERITS facts; recurse into body."""
        name = self.identifier_from_node(node)
        if not name:
            return

        qualified = ".".join([*scope_stack, name])
        definer = self._module_id
        if scope_stack:
            definer = f"{self.file_path}::{'.'.join(scope_stack)}"
        node_id = f"{self.file_path}::{qualified}"

        self._facts.append(
            SymbolDefinition(
                file_path=self.file_path,
                scope_stack=tuple(scope_stack),
                name=name,
                kind=NodeKind.CLASS,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                definer_id=definer,
            )
        )

        for child in node.children:
            if child.type not in _BASE_CLASS_NODE_TYPES:
                continue
            for base_name in self._get_base_classes_from_arg_list(child):
                resolved = self._resolve_base_class(base_name)
                self._facts.append(InheritsEdge(source_id=node_id, target=resolved))

        self._file_ctx.register_definition(name, node_id, is_class=True)

        new_scope = [*scope_stack, name]
        for child in node.children:
            self._dfs(child, scope_stack=new_scope)

    def _get_base_classes_from_arg_list(self, arg_list_node: TSNode) -> list[str]:
        """Extract base class names from arg list or extends_clause."""
        base_types = (
            "identifier",
            "dotted_name",
            "attribute",
            "type_identifier",
            "member_expression",
        )
        result: list[str] = []
        candidates = arg_list_node.named_children
        if not candidates and arg_list_node.type in (
            "extends_clause",
            "class_heritage",
        ):
            value = arg_list_node.child_by_field_name("value")
            if value:
                candidates = [value]
        for arg in candidates:
            if arg.type in base_types:
                name = self.node_text(arg)
                if name:
                    result.append(name)
        return result

    def _resolve_base_class(self, raw: str) -> str:
        """Resolve base class name through FileContext."""
        parts = raw.split(".")
        if len(parts) == 1:
            return self._file_ctx.resolve(raw) or raw
        prefix = parts[0]
        suffix = ".".join(parts[1:])
        prefix_resolved = self._file_ctx.resolve(prefix)
        if prefix_resolved:
            return f"{prefix_resolved}.{suffix}"
        return raw
