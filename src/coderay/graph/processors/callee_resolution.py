"""Shared callee resolution for call and decorator lowering."""

from __future__ import annotations

from collections.abc import Callable

from coderay.graph._utils import _BASE_CLASS_NODE_TYPES
from coderay.graph.facts import CallsEdge
from coderay.graph.lowering.session import LoweringSession
from coderay.graph.processors.cst_bases import list_base_names_from_arg_list
from coderay.parsing.base import BaseTreeSitterParser, TSNode
from coderay.parsing.languages import get_supported_extensions


class CalleeResolution:
    """Resolve call text to qualified targets; append CALLS facts."""

    def __init__(
        self,
        session: LoweringSession,
        parser: BaseTreeSitterParser,
        find_class_node: Callable[[str], TSNode | None],
    ) -> None:
        self._session = session
        self._parser = parser
        self._find_class_node = find_class_node
        self._supported_extensions = get_supported_extensions()

    def add_call_edges(
        self, caller_id: str, raw: str, callee_targets: list[str]
    ) -> None:
        del raw
        for callee_name in callee_targets:
            if callee_name:
                self._session.facts.add(
                    CallsEdge(source_id=caller_id, target=callee_name)
                )

    def resolve_callee_targets(self, raw: str, scope_stack: list[str]) -> list[str]:
        graph = self._parser.lang_cfg.graph
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
        for prefix in super_prefixes:
            if raw.startswith(prefix):
                method = raw[len(prefix) :]
                target = self.resolve_super_call(scope_stack, method)
                return [target] if target else [method]
        return None

    def resolve_self_targets(
        self, raw: str, scope_stack: list[str], self_prefix: str
    ) -> list[str] | None:
        if not self_prefix or not raw.startswith(self_prefix):
            return None
        suffix = raw.split(".", 1)[1]
        parts = suffix.split(".")
        method = parts[-1]
        fp = self._parser.file_path
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
                class_ref = fc.resolve_class_attribute(class_qualified, parts[0])
        if class_ref:
            return [f"{class_ref}.{method}"]
        return [method]

    def resolve_simple_name_targets(self, raw: str) -> list[str]:
        fc = self._session.file_ctx
        instance_class = fc.resolve_instance(raw)
        if instance_class:
            return [f"{instance_class}.__call__"]
        resolved = fc.resolve(raw)
        return [resolved] if resolved else [raw]

    def resolve_chain_targets(self, raw: str) -> list[str]:
        parts = raw.split(".")
        obj_name = parts[0]
        method_name = parts[-1]
        fc = self._session.file_ctx
        if len(parts) > 2:
            chain_refs = fc.resolve_chain(".".join(parts[:-1]))
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
        class_qualified = self.find_enclosing_class(scope_stack)
        if not class_qualified:
            return None
        base_name = self.get_first_base_class(class_qualified)
        if not base_name:
            return None
        fc = self._session.file_ctx
        base_resolved = fc.resolve(base_name)
        fp = self._parser.file_path
        return f"{base_resolved or f'{fp}::{base_name}'}.{method}"

    def get_first_base_class(self, class_qualified: str) -> str | None:
        target_class = class_qualified.split(".")[-1]
        class_node = self._find_class_node(target_class)
        if not class_node:
            return None
        for child in class_node.children:
            if child.type not in _BASE_CLASS_NODE_TYPES:
                continue
            bases = list_base_names_from_arg_list(child, self._parser.node_text)
            if bases:
                return bases[0]
        return None

    def find_enclosing_class(self, scope_stack: list[str]) -> str | None:
        fc = self._session.file_ctx
        for i in range(len(scope_stack) - 1, -1, -1):
            if fc.is_class(scope_stack[i]):
                return ".".join(scope_stack[: i + 1])
        return None
