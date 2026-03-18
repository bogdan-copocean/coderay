"""Call handling: CALLS edges, resolution, filtering."""

from __future__ import annotations

import builtins
from typing import Any

from coderay.core.models import EdgeKind, GraphEdge
from coderay.graph._utils import _BASE_CLASS_NODE_TYPES
from coderay.parsing.languages import get_supported_extensions

TSNode = Any

# Re-exported for tests
_PYTHON_BUILTINS: frozenset[str] = frozenset(
    name for name in dir(builtins) if not name.startswith("_")
)


class CallHandlerMixin:
    """Handle calls: CALLS edges and instantiation tracking."""

    def _caller_id_from_scope(self, scope_stack: list[str]) -> str:
        """Return caller node ID for scope."""
        if scope_stack:
            return f"{self.file_path}::{'.'.join(scope_stack)}"
        return self._module_id

    def _handle_call(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Create CALLS edge to resolved callee."""
        caller_id = self._caller_id_from_scope(scope_stack)

        callee_node = node.child_by_field_name("function")
        if callee_node is None:
            return
        raw_callee = self.node_text(callee_node)
        if not raw_callee:
            return

        callee_targets = self._resolve_callee_targets(raw_callee, scope_stack)

        for callee_name in callee_targets:
            if self._is_excluded(callee_name, raw_callee):
                continue
            if callee_name:
                self._edges.append(
                    GraphEdge(
                        source=caller_id,
                        target=callee_name,
                        kind=EdgeKind.CALLS,
                    )
                )

        self._maybe_track_instantiation(node, raw_callee)

    def _resolve_callee_targets(self, raw: str, scope_stack: list[str]) -> list[str]:
        """Resolve callee to qualified targets."""
        result = self._resolve_super_targets(raw, scope_stack)
        if result is not None:
            return result
        result = self._resolve_self_targets(raw, scope_stack)
        if result is not None:
            return result
        parts = raw.split(".")
        if len(parts) == 1:
            return self._resolve_simple_name_targets(raw)
        return self._resolve_chain_targets(raw)

    def _resolve_super_targets(
        self, raw: str, scope_stack: list[str]
    ) -> list[str] | None:
        """Resolve super().method (Python) or super.method (JS) to parent method."""
        if raw.startswith("super()."):
            method = raw[len("super().") :]
        elif raw.startswith("super."):
            method = raw[len("super.") :]
        else:
            return None
        parent_target = self._resolve_super_call(scope_stack, method)
        return [parent_target] if parent_target else [method]

    def _resolve_self_targets(
        self, raw: str, scope_stack: list[str]
    ) -> list[str] | None:
        """Resolve self.method() or this.method() via instance/class attrs."""
        if not self._lc.self_prefixes or not raw.startswith(self._lc.self_prefixes):
            return None
        suffix = raw.split(".", 1)[1]
        parts = suffix.split(".")
        method = parts[-1]

        if len(parts) == 1:
            class_qualified = self._find_enclosing_class(scope_stack)
            if class_qualified:
                return [f"{self.file_path}::{class_qualified}.{method}"]

        prefix = next((p for p in self._lc.self_prefixes if raw.startswith(p)), "self.")
        instance_key = prefix + ".".join(parts[:-1])
        class_ref = self._file_ctx.resolve_instance(instance_key)
        if not class_ref:
            class_qualified = self._find_enclosing_class(scope_stack)
            if class_qualified and len(parts) == 2:
                attr_name = parts[0]
                class_ref = self._file_ctx.resolve_class_attribute(
                    class_qualified, attr_name
                )
        if class_ref:
            return [f"{class_ref}.{method}"]
        return [method]

    def _resolve_simple_name_targets(self, raw: str) -> list[str]:
        """Resolve simple name via alias/import/instance."""
        name = raw
        instance_class = self._file_ctx.resolve_instance(name)
        if instance_class:
            return [f"{instance_class}.__call__"]
        resolved = self._file_ctx.resolve(name)
        return [resolved] if resolved else [name]

    def _resolve_chain_targets(self, raw: str) -> list[str]:
        """Resolve obj.attr.method() chains."""
        parts = raw.split(".")
        obj_name = parts[0]
        method_name = parts[-1]

        if len(parts) > 2:
            chain = ".".join(parts[:-1])
            chain_refs = self._file_ctx.resolve_chain(chain)
            if chain_refs:
                return [f"{ref}.{method_name}" for ref in chain_refs]

        method_targets = self._file_ctx.resolve_method_calls(obj_name, method_name)
        if method_targets:
            return method_targets

        obj_resolved = self._file_ctx.resolve(obj_name)
        if obj_resolved:
            tail = ".".join(parts[1:])
            _, ext = obj_resolved.rsplit(".", 1) if "." in obj_resolved else ("", "")
            supported = get_supported_extensions()
            if ext and f".{ext}" in supported:
                return [f"{obj_resolved}::{tail}"]
            return [f"{obj_resolved}.{tail}"]

        return [method_name]

    def _is_excluded(self, resolved: str, raw: str) -> bool:
        """Return True if callee is excluded (builtins, typing, etc.)."""
        if "::" in resolved:
            module_part = resolved.split("::")[0]
            if module_part in self._excluded_modules:
                return True
        bare = raw.rsplit(".", 1)[-1]
        if resolved != bare:
            return False
        return bare in self._lc.builtins

    def _resolve_super_call(self, scope_stack: list[str], method: str) -> str | None:
        """Resolve super().method() to parent method."""
        class_qualified = self._find_enclosing_class(scope_stack)
        if not class_qualified:
            return None
        # Find the class node and its first base class
        base_name = self._get_first_base_class(class_qualified)
        if not base_name:
            return None
        base_resolved = self._file_ctx.resolve(base_name)
        if not base_resolved:
            base_resolved = f"{self.file_path}::{base_name}"
        return f"{base_resolved}.{method}"

    def _get_first_base_class(self, class_qualified: str) -> str | None:
        """Return first base class name for class."""
        tree = self.get_tree()
        target_class = class_qualified.split(".")[-1]
        class_types = self._lc.class_scope_types + self._lc.extra_class_scope_types

        def find_class(node: TSNode) -> TSNode | None:
            if node.type in class_types:
                name_node = node.child_by_field_name("name") or (
                    node.named_children[0] if node.named_children else None
                )
                if name_node and self.node_text(name_node) == target_class:
                    return node
            for child in node.children:
                found = find_class(child)
                if found:
                    return found
            return None

        class_node = find_class(tree.root_node)
        if not class_node:
            return None
        for child in class_node.children:
            if child.type not in _BASE_CLASS_NODE_TYPES:
                continue
            bases = self._get_base_classes_from_arg_list(child)
            if bases:
                return bases[0]
        return None

    def _find_enclosing_class(self, scope_stack: list[str]) -> str | None:
        """Find innermost enclosing class from scope stack."""
        for i in range(len(scope_stack) - 1, -1, -1):
            if self._file_ctx.is_class(scope_stack[i]):
                return ".".join(scope_stack[: i + 1])
        return None

    def _maybe_track_instantiation(self, call_node: TSNode, raw_callee: str) -> None:
        """Track x = SomeClass() as instance for call resolution."""
        parent = call_node.parent
        if parent is None or parent.type not in self._lc.assignment_types:
            return

        lhs = (
            parent.child_by_field_name("name")
            or parent.child_by_field_name("left")
            or (parent.children[0] if parent.children else None)
        )
        if lhs is None:
            return

        if lhs.type == "identifier":
            var_name = self.node_text(lhs)
        elif lhs.type == "attribute":
            var_name = self.node_text(lhs)
            if not self._lc.self_prefixes or not var_name.startswith(
                self._lc.self_prefixes
            ):
                return  # Only track self.attr = X(), not other.attr = X()
        else:
            return

        callee_base = raw_callee.rsplit(".", 1)[-1]  # "ApiClient.create" → "create"
        if not callee_base:
            return

        resolved = self._file_ctx.resolve(callee_base)
        is_known_class = self._file_ctx.is_class(callee_base)
        is_likely_class = bool(callee_base[0].isupper() and resolved is not None)

        # Only register if this looks like a class instantiation
        if is_known_class or is_likely_class:
            self._file_ctx.register_instance(var_name, resolved or callee_base)
            # Also register for class (enables service.client.get resolution)
            if self._lc.self_prefixes and var_name.startswith(self._lc.self_prefixes):
                func_node = self._get_enclosing_function_node(call_node)
                if func_node:
                    class_qualified = self._find_enclosing_class_from_node(func_node)
                    if class_qualified:
                        attr_name = var_name.split(".", 1)[1].split(".")[0]
                        self._file_ctx.register_class_attribute(
                            class_qualified, attr_name, resolved or callee_base
                        )

    def _handle_decorator(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Create CALLS edge to decorator target (Python only)."""
        text = self.node_text(node).strip()
        if not text or not text.startswith("@"):
            return
        # Strip @ and any trailing call parens: @foo.bar(args) -> foo.bar
        target_raw = text[1:].strip()
        if "(" in target_raw:
            target_raw = target_raw[: target_raw.index("(")].strip()
        if not target_raw:
            return

        callee_targets = self._resolve_callee_targets(target_raw, scope_stack)
        caller_id = self._caller_id_from_scope(scope_stack)
        for callee_name in callee_targets:
            if self._is_excluded(callee_name, target_raw):
                continue
            if callee_name:
                self._edges.append(
                    GraphEdge(
                        source=caller_id,
                        target=callee_name,
                        kind=EdgeKind.CALLS,
                    )
                )
