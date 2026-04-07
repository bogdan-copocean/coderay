"""Shared callee resolution for call and decorator lowering."""

from __future__ import annotations

from collections.abc import Callable

from coderay.graph._utils import _BASE_CLASS_NODE_TYPES
from coderay.graph.facts import CallsEdge
from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead
from coderay.graph.processors.cst_bases import list_base_names_from_arg_list
from coderay.parsing.base import TSNode


class CalleeResolution:
    """Resolve call text to qualified targets; append CALLS facts."""

    def __init__(
        self,
        session: LoweringSession,
        syntax: SyntaxRead,
        find_class_node: Callable[[str], TSNode | None],
        supported_extensions: set[str],
    ) -> None:
        self._session = session
        self._syntax = syntax
        self._find_class_node = find_class_node
        self._supported_extensions = supported_extensions

    def add_call_edges(
        self, caller_id: str, raw: str, callee_targets: list[str]
    ) -> None:
        """Append CALLS facts for resolved targets."""
        del raw
        for callee_name in callee_targets:
            if callee_name:
                self._session.facts.add(
                    CallsEdge(source_id=caller_id, target=callee_name)
                )

    def resolve_callee_targets(self, raw: str, scope_stack: list[str]) -> list[str]:
        """Resolve callee to qualified targets."""
        graph = self._syntax.lang_cfg.graph
        result = self.resolve_super_targets(raw, scope_stack, graph.super_prefixes)
        if result is not None:
            return result
        result = self.resolve_self_targets(raw, scope_stack, graph.self_prefix)
        if result is not None:
            return result
        parts = raw.split(".")
        if len(parts) == 1:
            return self.resolve_simple_name_targets(raw)
        return self.resolve_chain_targets(raw)

    def resolve_super_targets(
        self, raw: str, scope_stack: list[str], super_prefixes: tuple[str, ...]
    ) -> list[str] | None:
        """Resolve super().method() style calls."""
        for prefix in super_prefixes:
            if raw.startswith(prefix):
                method = raw[len(prefix) :]
                target = self.resolve_super_call(scope_stack, method)
                return [target] if target else [method]
        return None

    def resolve_self_targets(
        self, raw: str, scope_stack: list[str], self_prefix: str
    ) -> list[str] | None:
        """Resolve self.method() style calls."""
        if not self_prefix or not raw.startswith(self_prefix):
            return None
        suffix = raw.split(".", 1)[1]
        parts = suffix.split(".")
        method = parts[-1]
        fp = self._syntax.file_path
        fc = self._session.file_ctx
        if len(parts) == 1:
            class_qualified = self.find_enclosing_class(scope_stack)
            if class_qualified:
                return [f"{fp}::{class_qualified}.{method}"]
        instance_key = self_prefix + ".".join(parts[:-1])
        class_ref = fc.resolve_instance(instance_key)
        if not class_ref:
            class_qualified = self.find_enclosing_class(scope_stack)
            if class_qualified and len(parts) == 2:
                attr_name = parts[0]
                class_ref = fc.resolve_class_attribute(class_qualified, attr_name)
        if class_ref:
            return [f"{class_ref}.{method}"]
        return [method]

    def resolve_simple_name_targets(self, raw: str) -> list[str]:
        """Resolve a bare name call."""
        name = raw
        fc = self._session.file_ctx
        instance_class = fc.resolve_instance(name)
        if instance_class:
            return [f"{instance_class}.__call__"]
        resolved = fc.resolve(name)
        return [resolved] if resolved else [name]

    def resolve_chain_targets(self, raw: str) -> list[str]:
        """Resolve dotted call chain."""
        parts = raw.split(".")
        obj_name = parts[0]
        method_name = parts[-1]
        fc = self._session.file_ctx
        if len(parts) > 2:
            chain = ".".join(parts[:-1])
            chain_refs = fc.resolve_chain(chain)
            if chain_refs:
                return [f"{ref}.{method_name}" for ref in chain_refs]
        method_targets = fc.resolve_method_calls(obj_name, method_name)
        if method_targets:
            return method_targets
        obj_resolved = fc.resolve(obj_name)
        if obj_resolved:
            tail = ".".join(parts[1:])
            _, ext = obj_resolved.rsplit(".", 1) if "." in obj_resolved else ("", "")
            if ext and f".{ext}" in self._supported_extensions:
                return [f"{obj_resolved}::{tail}"]
            return [f"{obj_resolved}.{tail}"]
        return [method_name]

    def resolve_super_call(self, scope_stack: list[str], method: str) -> str | None:
        """Resolve super().method() to parent class method."""
        class_qualified = self.find_enclosing_class(scope_stack)
        if not class_qualified:
            return None
        base_name = self.get_first_base_class(class_qualified)
        if not base_name:
            return None
        fc = self._session.file_ctx
        base_resolved = fc.resolve(base_name)
        fp = self._syntax.file_path
        if not base_resolved:
            base_resolved = f"{fp}::{base_name}"
        return f"{base_resolved}.{method}"

    def get_first_base_class(self, class_qualified: str) -> str | None:
        """First base class name for inheritance (super resolution)."""
        target_class = class_qualified.split(".")[-1]
        class_node = self._find_class_node(target_class)
        if not class_node:
            return None
        nt = self._syntax.node_text
        for child in class_node.children:
            if child.type not in _BASE_CLASS_NODE_TYPES:
                continue
            bases = list_base_names_from_arg_list(child, nt)
            if bases:
                return bases[0]
        return None

    def find_enclosing_class(self, scope_stack: list[str]) -> str | None:
        """Innermost enclosing class from scope stack."""
        fc = self._session.file_ctx
        for i in range(len(scope_stack) - 1, -1, -1):
            if fc.is_class(scope_stack[i]):
                return ".".join(scope_stack[: i + 1])
        return None
