"""Call handling for graph extraction.

Creates CALLS edges (caller -> callee) from resolved call expressions.
Resolves callees via FileContext (instance tracking, aliases, class attrs).
Also tracks x = SomeClass() for instantiation. Filters out builtins and
excluded modules.
"""

from __future__ import annotations

import builtins
from typing import Any

from coderay.core.models import EdgeKind, GraphEdge
from coderay.parsing.languages import get_supported_extensions

TSNode = Any

# Builtins (print, len, etc.) are filtered from CALLS edges
_PYTHON_BUILTINS: frozenset[str] = frozenset(
    name for name in dir(builtins) if not name.startswith("_")
)


class CallHandlerMixin:
    """Handles call expressions: CALLS edges and instantiation tracking."""

    def _caller_id_from_scope(self, scope_stack: list[str]) -> str:
        """Return the caller node ID for the given scope stack."""
        if scope_stack:
            return f"{self.file_path}::{'.'.join(scope_stack)}"
        return self._module_id

    def _handle_call(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Create a CALLS edge from the enclosing scope to the resolved callee."""
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
        """Resolve a callee expression to a qualified target for CALLS edges."""
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
        """Resolve super().method() to parent class method."""
        if not raw.startswith("super()."):
            return None
        method = raw[len("super().") :]
        parent_target = self._resolve_super_call(scope_stack, method)
        return [parent_target] if parent_target else [method]

    def _resolve_self_targets(
        self, raw: str, scope_stack: list[str]
    ) -> list[str] | None:
        """Resolve self.method() or self.attr.method() via instance/class attrs."""
        if not raw.startswith(("self.", "this.")):
            return None
        suffix = raw.split(".", 1)[1]
        parts = suffix.split(".")
        method = parts[-1]

        if len(parts) == 1:
            class_qualified = self._find_enclosing_class(scope_stack)
            if class_qualified:
                return [f"{self.file_path}::{class_qualified}.{method}"]

        prefix = "self." if raw.startswith("self.") else "this."
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
        """Resolve simple name func() or obj() via alias/import/instance."""
        name = raw
        instance_class = self._file_ctx.resolve_instance(name)
        if instance_class:
            return [f"{instance_class}.__call__"]
        resolved = self._file_ctx.resolve(name)
        return [resolved] if resolved else [name]

    def _resolve_chain_targets(self, raw: str) -> list[str]:
        """Resolve obj.method(), obj.attr.method(), or obj.attr() chains."""
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
        """Check whether a resolved callee belongs to an excluded module."""
        # Excluded: typing, abc, __future__; also bare builtins (print, len)
        if "::" in resolved:
            module_part = resolved.split("::")[0]
            if module_part in self._excluded_modules:
                return True
        bare = raw.rsplit(".", 1)[-1]
        return resolved == bare and bare in _PYTHON_BUILTINS

    def _resolve_super_call(self, scope_stack: list[str], method: str) -> str | None:
        """Resolve super().method() to the parent class's method."""
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
        """Get the first base class name for a class in the current file."""
        tree = self.get_tree()
        target_class = class_qualified.split(".")[-1]

        for node in tree.root_node.children:
            if node.type not in self._ctx.lang_cfg.class_scope_types:
                continue
            name_node = node.child_by_field_name("name") or (
                node.named_children[0] if node.named_children else None
            )
            if not name_node or self.node_text(name_node) != target_class:
                continue
            for child in node.children:
                if child.type not in ("argument_list", "superclass", "extends_clause"):
                    continue
                bases = self._get_base_classes_from_arg_list(child)
                if bases:
                    return bases[0]
            break
        return None

    def _find_enclosing_class(self, scope_stack: list[str]) -> str | None:
        """Find the innermost enclosing class name from the scope stack.

        scope_stack = ["Outer", "Inner", "method"] → "Outer.Inner"
        """
        for i in range(len(scope_stack) - 1, -1, -1):
            if self._file_ctx.is_class(scope_stack[i]):
                return ".".join(scope_stack[: i + 1])
        return None

    def _maybe_track_instantiation(self, call_node: TSNode, raw_callee: str) -> None:
        """Track ``x = SomeClass()`` or ``self.attr = SomeClass()`` as instance.

        Called after _handle_call; checks if this call is the RHS of an
        assignment. If so, registers the LHS as an instance of the callee.
        """
        parent = call_node.parent
        if parent is None or parent.type != "assignment":
            return  # Not an assignment RHS

        lhs = parent.children[0] if parent.children else None
        if lhs is None:
            return

        if lhs.type == "identifier":
            var_name = self.node_text(lhs)
        elif lhs.type == "attribute":
            var_name = self.node_text(lhs)
            if not var_name.startswith(("self.", "this.")):
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
            if var_name.startswith(("self.", "this.")):
                func_node = self._get_enclosing_function_node(call_node)
                if func_node:
                    class_qualified = self._find_enclosing_class_from_node(func_node)
                    if class_qualified:
                        attr_name = var_name.split(".", 1)[1].split(".")[0]
                        self._file_ctx.register_class_attribute(
                            class_qualified, attr_name, resolved or callee_base
                        )

    def _handle_decorator(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Create a CALLS edge from the enclosing scope to the decorator target.

        @my_decorator and @my_decorator() both imply a call at definition time.
        """
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
