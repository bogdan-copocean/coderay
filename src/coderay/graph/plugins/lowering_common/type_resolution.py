"""Shared type hint resolution for DI (language-agnostic core)."""

from __future__ import annotations

from typing import Any

TSNode = Any


class TypeResolutionCoreMixin:
    """Resolve type annotations via FileContext; subclasses supply symbol finders."""

    def _resolve_type_text(self, type_text: str | None) -> str | None:
        """Resolve type annotation to qualified class reference."""
        refs = self._resolve_type_texts(type_text)
        return refs[0] if refs else None

    def _resolve_type_texts(
        self, type_text: str | None, *, enclosing_func_node: TSNode | None = None
    ) -> list[str]:
        """Resolve type annotation to qualified class refs."""
        if not type_text:
            return []
        text = type_text.strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text == "Self" and enclosing_func_node:
            class_qualified = self._find_enclosing_class_from_node(enclosing_func_node)
            if class_qualified:
                return [f"{self.file_path}::{class_qualified}"]
            return []
        parts = [p.strip() for p in text.split("|")]
        result: list[str] = []
        for part in parts:
            if not part:
                continue
            if part in ("None", "NoneType"):
                continue
            if "." in part and not part[0].isupper():
                alias, _, attr = part.partition(".")
                if attr and attr[0].isupper():
                    resolved_alias = self._file_ctx.resolve(alias)
                    if resolved_alias:
                        result.append(f"{resolved_alias}::{attr}")
                continue
            if not part[0].isupper():
                continue
            resolved = self._file_ctx.resolve(part)
            result.append(resolved or f"{self.file_path}::{part}")
        return result

    def _find_enclosing_class_from_node(self, node: TSNode) -> str | None:
        """Find innermost enclosing class qualified name."""
        current = node.parent
        class_names: list[str] = []
        while current:
            if current.type in self._ctx.lang_cfg.class_scope_types:
                name_node = current.child_by_field_name("name") or (
                    current.named_children[0] if current.named_children else None
                )
                if name_node:
                    name = self.node_text(name_node)
                    if name:
                        class_names.append(name)
            current = current.parent
        if not class_names:
            return None
        class_names.reverse()
        return ".".join(class_names)

    def _extract_type_from_typed_param(
        self, param_node: TSNode
    ) -> tuple[str, list[str]] | None:
        """Extract (param_name, type_refs) from typed_parameter node."""
        name_node = param_node.child_by_field_name("name") or (
            param_node.children[0] if param_node.children else None
        )
        if not name_node:
            return None
        pname = self.node_text(name_node)
        type_node = param_node.child_by_field_name("type")
        if type_node is None:
            for c in param_node.children:
                if c.type == "type":
                    type_node = c
                    break
        if not type_node:
            return None
        enclosing = None
        parent = param_node.parent
        if parent and parent.parent:
            enclosing = parent.parent
        type_refs = self._resolve_type_texts(
            self.node_text(type_node), enclosing_func_node=enclosing
        )
        return (pname, type_refs) if type_refs else None

    def _get_function_return_type(self, callee_name: str) -> str | None:
        """Resolve function/method return type from annotation."""
        if "." in callee_name:
            class_name, method_name = callee_name.split(".", 1)
            func_node = self._find_method_in_class(class_name, method_name)
        else:
            func_node = self._find_top_level_function(callee_name)
        return self._get_return_type_from_func_node(func_node) if func_node else None

    def _get_return_type_from_func_node(self, func_node: TSNode) -> str | None:
        """Extract return type from function definition."""
        type_node = func_node.child_by_field_name(
            "return_type"
        ) or func_node.child_by_field_name("type")
        if not type_node:
            return None
        refs = self._resolve_type_texts(
            self.node_text(type_node), enclosing_func_node=func_node
        )
        return refs[0] if refs else None

    def _get_enclosing_function_node(self, node: TSNode) -> TSNode | None:
        """Walk up tree to find enclosing function definition."""
        current = node.parent
        while current:
            if current.type in self._ctx.lang_cfg.function_scope_types:
                return current
            current = current.parent
        return None

    def _get_typed_parameters(self, func_node: TSNode) -> list[tuple[str, list[str]]]:
        """Collect (param_name, type_refs) for typed parameters."""
        params = func_node.child_by_field_name("parameters")
        if not params:
            return []
        param_types = self._desc.typed_param_types
        result: list[tuple[str, list[str]]] = []
        for child in params.children:
            if child.type in param_types:
                extracted = self._extract_type_from_typed_param(child)
                if extracted:
                    result.append(extracted)
        return result

    def _get_parameter_type_hint(
        self, func_node: TSNode, param_name: str
    ) -> str | None:
        """Get parameter type hint (constructor/setter injection)."""
        params = func_node.child_by_field_name("parameters")
        if not params:
            return None
        param_types = self._desc.typed_param_types
        for child in params.children:
            if child.type in param_types:
                extracted = self._extract_type_from_typed_param(child)
                if extracted and extracted[0] == param_name:
                    refs = extracted[1]
                    return refs[0] if refs else None
        return None
