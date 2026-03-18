"""Definition handling: DEFINES, INHERITS edges, scope."""

from __future__ import annotations

from typing import Any

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.graph._utils import _BASE_CLASS_NODE_TYPES

TSNode = Any


class DefinitionHandlerMixin:
    """Handle class/function definitions: DEFINES, INHERITS, scope."""

    def _handle_function_def(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Create FUNCTION node and DEFINES edge; recurse into body."""
        parent = node.parent if node.type == "arrow_function" else None
        name = self.identifier_from_node(node, parent)
        if not name:
            return

        # scope_stack = [] for top-level, ["ClassName"] for methods
        qualified = ".".join([*scope_stack, name])
        node_id = f"{self.file_path}::{qualified}"

        self._nodes.append(
            GraphNode(
                id=node_id,
                kind=NodeKind.FUNCTION,
                file_path=self.file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                name=name,
                qualified_name=qualified,
            )
        )
        definer = self._module_id
        if scope_stack:
            definer = f"{self.file_path}::{'.'.join(scope_stack)}"
        self._edges.append(
            GraphEdge(source=definer, target=node_id, kind=EdgeKind.DEFINES)
        )

        # Register so calls like my_func() or ClassName.method() resolve
        if not scope_stack:
            self._file_ctx.register_definition(name, node_id)
        else:
            self._file_ctx.register_definition(qualified, node_id)

        # Param injection: processor: DataProcessor → processor.process() resolves
        for param_name, type_refs in self._get_typed_parameters(node):
            if len(type_refs) == 1:
                self._file_ctx.register_instance(param_name, type_refs[0])
            else:
                self._file_ctx.register_instance_union(param_name, type_refs)

        # Property injection: @property def repo() -> Repo → self.repo.save() resolves
        if self._is_property(node) and scope_stack:
            class_qualified = ".".join(scope_stack)
            return_type = self._get_return_type_from_func_node(node)
            if return_type:
                self._file_ctx.register_class_attribute(
                    class_qualified, name, return_type
                )

        # Recurse into body; new scope so nested defs get correct qualified names
        new_scope = [*scope_stack, name]
        for child in node.children:
            self._dfs(child, scope_stack=new_scope)

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

    def _handle_class_def(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Create CLASS node, DEFINES + INHERITS edges; recurse into body."""
        name = self.identifier_from_node(node)
        if not name:
            return

        qualified = ".".join([*scope_stack, name])
        node_id = f"{self.file_path}::{qualified}"

        self._nodes.append(
            GraphNode(
                id=node_id,
                kind=NodeKind.CLASS,
                file_path=self.file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                name=name,
                qualified_name=qualified,
            )
        )
        definer = self._module_id
        if scope_stack:
            definer = f"{self.file_path}::{'.'.join(scope_stack)}"
        self._edges.append(
            GraphEdge(source=definer, target=node_id, kind=EdgeKind.DEFINES)
        )

        for child in node.children:
            if child.type not in _BASE_CLASS_NODE_TYPES:
                continue
            for base_name in self._get_base_classes_from_arg_list(child):
                resolved = self._resolve_base_class(base_name)
                self._edges.append(
                    GraphEdge(
                        source=node_id,
                        target=resolved,
                        kind=EdgeKind.INHERITS,
                    )
                )

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
        if not candidates and arg_list_node.type in ("extends_clause", "class_heritage"):
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
