"""Pure callee resolution: bindings + parser text → target node IDs."""

from __future__ import annotations

from coderay.graph.handlers.helpers import (
    BASE_CLASS_NODE_TYPES,
    list_base_names_from_arg_list,
)
from coderay.graph.lowering.name_bindings import OONameBindings
from coderay.parsing.base import BaseTreeSitterParser
from coderay.parsing.languages import get_supported_extensions


class CalleeResolver:
    """Resolve a raw callee string to qualified target node IDs.

    Takes ``OONameBindings`` and a parser (text only).
    Produces ``list[str]`` — no side effects, no fact emission.
    """

    def __init__(self, bindings: OONameBindings, parser: BaseTreeSitterParser) -> None:
        self._bindings = bindings
        self._parser = parser
        self._supported_extensions = get_supported_extensions()

    def resolve(self, raw: str, scope_stack: list[str]) -> list[str]:
        """Return qualified target IDs for *raw* callee text."""
        graph_cfg = self._parser.lang_cfg.graph
        result = self._resolve_super(raw, scope_stack, graph_cfg.super_prefixes)
        if result is not None:
            return result
        result = self._resolve_self(raw, scope_stack, graph_cfg.self_prefix)
        if result is not None:
            return result
        return self._resolve_simple(raw) if "." not in raw else self._resolve_chain(raw)

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------

    def _resolve_super(
        self, raw: str, scope_stack: list[str], super_prefixes: tuple[str, ...]
    ) -> list[str] | None:
        for prefix in super_prefixes:
            if raw.startswith(prefix):
                method = raw[len(prefix) :]
                target = self._resolve_super_call(scope_stack, method)
                return [target] if target else [method]
        return None

    def _resolve_self(
        self, raw: str, scope_stack: list[str], self_prefix: str
    ) -> list[str] | None:
        if not self_prefix or not raw.startswith(self_prefix):
            return None
        suffix = raw.split(".", 1)[1]
        parts = suffix.split(".")
        method = parts[-1]
        fp = self._parser.file_path
        b = self._bindings
        if len(parts) == 1:
            class_qualified = self._find_enclosing_class(scope_stack)
            if class_qualified:
                return [f"{fp}::{class_qualified}.{method}"]
        instance_key = self_prefix + ".".join(parts[:-1])
        class_ref = b.resolve_instance(instance_key)
        if not class_ref:
            class_qualified = self._find_enclosing_class(scope_stack)
            if class_qualified and len(parts) == 2:
                class_ref = b.resolve_class_attribute(class_qualified, parts[0])
        if class_ref:
            return [f"{class_ref}.{method}"]
        return [method]

    def _resolve_simple(self, raw: str) -> list[str]:
        b = self._bindings
        instance_class = b.resolve_instance(raw)
        if instance_class:
            return [f"{instance_class}.__call__"]
        resolved = b.resolve(raw)
        return [resolved] if resolved else [raw]

    def _resolve_chain(self, raw: str) -> list[str]:
        parts = raw.split(".")
        obj_name = parts[0]
        method_name = parts[-1]
        b = self._bindings
        if len(parts) > 2:
            chain_refs = b.resolve_chain(".".join(parts[:-1]))
            if chain_refs:
                return [f"{ref}.{method_name}" for ref in chain_refs]
        method_targets = b.resolve_method_calls(obj_name, method_name)
        if method_targets:
            return method_targets
        obj_resolved = b.resolve(obj_name)
        if obj_resolved:
            tail = ".".join(parts[1:])
            _, ext = obj_resolved.rsplit(".", 1) if "." in obj_resolved else ("", "")
            if ext and f".{ext}" in self._supported_extensions:
                return [f"{obj_resolved}::{tail}"]
            return [f"{obj_resolved}.{tail}"]
        return [method_name]

    # ------------------------------------------------------------------
    # Super / enclosing class helpers
    # ------------------------------------------------------------------

    def _resolve_super_call(self, scope_stack: list[str], method: str) -> str | None:
        class_qualified = self._find_enclosing_class(scope_stack)
        if not class_qualified:
            return None
        base_name = self._get_first_base_class(class_qualified)
        if not base_name:
            return None
        base_resolved = self._bindings.resolve(base_name)
        fp = self._parser.file_path
        return f"{base_resolved or f'{fp}::{base_name}'}.{method}"

    def _get_first_base_class(self, class_qualified: str) -> str | None:
        from coderay.graph.handlers.helpers import find_class_node

        target_class = class_qualified.split(".")[-1]
        class_node = find_class_node(self._parser, target_class)
        if not class_node:
            return None
        for child in class_node.children:
            if child.type not in BASE_CLASS_NODE_TYPES:
                continue
            bases = list_base_names_from_arg_list(child, self._parser.node_text)
            if bases:
                return bases[0]
        return None

    def _find_enclosing_class(self, scope_stack: list[str]) -> str | None:
        for i in range(len(scope_stack) - 1, -1, -1):
            if self._bindings.is_class(scope_stack[i]):
                return ".".join(scope_stack[: i + 1])
        return None
