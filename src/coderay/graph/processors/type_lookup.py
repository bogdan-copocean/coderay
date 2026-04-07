"""Annotation resolution: ``TypeLookup`` Protocol; ``_TypeLookupCore`` implements."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead
from coderay.graph.processors.type_text_resolve import (
    is_bare_self_annotation,
    resolve_annotation_type_text,
    resolve_annotation_type_texts,
)
from coderay.parsing.base import TSNode


class TypeLookup(Protocol):
    """Annotation resolution and CST function lookup (not a node processor)."""

    def find_method_in_class_body(
        self, class_node: TSNode, method_name: str
    ) -> TSNode | None: ...

    def find_top_level_function(self, func_name: str) -> TSNode | None: ...

    def resolve_type_text(self, type_text: str | None) -> str | None: ...

    def resolve_type_texts(
        self, type_text: str | None, *, enclosing_func_node: TSNode | None = None
    ) -> list[str]: ...

    def find_enclosing_class_from_node(self, node: TSNode) -> str | None: ...

    def extract_type_from_typed_param(
        self, param_node: TSNode
    ) -> tuple[str, list[str]] | None: ...

    def get_function_return_type(self, callee_name: str) -> str | None: ...

    def get_return_type_from_func_node(self, func_node: TSNode) -> str | None: ...

    def get_enclosing_function_node(self, node: TSNode) -> TSNode | None: ...

    def get_typed_parameters(
        self, func_node: TSNode
    ) -> list[tuple[str, list[str]]]: ...

    def get_parameter_type_hint(
        self, func_node: TSNode, param_name: str
    ) -> str | None: ...

    def find_method_in_class(
        self, class_name: str, method_name: str
    ) -> TSNode | None: ...


class _TypeLookupCore:
    """Shared type resolution; language classes override class/top-level lookup."""

    def __init__(
        self,
        session: LoweringSession,
        syntax: SyntaxRead,
        find_class_node: Callable[[str], TSNode | None],
    ) -> None:
        self._session = session
        self._syntax = syntax
        self._find_class_node = find_class_node

    def find_method_in_class_body(
        self, class_node: TSNode, method_name: str
    ) -> TSNode | None:
        """Return method node inside class body, or None."""
        raise NotImplementedError

    def find_top_level_function(self, func_name: str) -> TSNode | None:
        """Return module-scope function node by name, or None."""
        raise NotImplementedError

    def resolve_type_text(self, type_text: str | None) -> str | None:
        """Resolve annotation to a single qualified class ref."""
        return resolve_annotation_type_text(
            type_text,
            file_path=self._syntax.file_path,
            resolve=self._session.file_ctx.resolve,
        )

    def resolve_type_texts(
        self, type_text: str | None, *, enclosing_func_node: TSNode | None = None
    ) -> list[str]:
        """Resolve annotation text to qualified class refs."""
        use_self = bool(enclosing_func_node) and is_bare_self_annotation(type_text)
        enc = (
            self.find_enclosing_class_from_node(enclosing_func_node)
            if use_self
            else None
        )
        return resolve_annotation_type_texts(
            type_text,
            file_path=self._syntax.file_path,
            resolve=self._session.file_ctx.resolve,
            use_self_semantics=use_self,
            enclosing_class_qualified=enc,
        )

    def find_enclosing_class_from_node(self, node: TSNode) -> str | None:
        """Walk up to innermost enclosing class qualified name."""
        current = node.parent
        class_names: list[str] = []
        class_scope_types = self._syntax._ctx.lang_cfg.cst.class_scope_types
        while current:
            if current.type in class_scope_types:
                name_node = current.child_by_field_name("name") or (
                    current.named_children[0] if current.named_children else None
                )
                if name_node:
                    name = self._syntax.node_text(name_node)
                    if name:
                        class_names.append(name)
            current = current.parent
        if not class_names:
            return None
        class_names.reverse()
        return ".".join(class_names)

    def extract_type_from_typed_param(
        self, param_node: TSNode
    ) -> tuple[str, list[str]] | None:
        """Extract (param_name, type_refs) from a typed parameter node."""
        name_node = param_node.child_by_field_name("name") or (
            param_node.children[0] if param_node.children else None
        )
        if not name_node:
            return None
        pname = self._syntax.node_text(name_node)
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
        type_refs = self.resolve_type_texts(
            self._syntax.node_text(type_node), enclosing_func_node=enclosing
        )
        return (pname, type_refs) if type_refs else None

    def get_function_return_type(self, callee_name: str) -> str | None:
        """Resolve function/method return type from its annotation."""
        if "." in callee_name:
            class_name, method_name = callee_name.split(".", 1)
            func_node = self.find_method_in_class(class_name, method_name)
        else:
            func_node = self.find_top_level_function(callee_name)
        return self.get_return_type_from_func_node(func_node) if func_node else None

    def get_return_type_from_func_node(self, func_node: TSNode) -> str | None:
        """Extract return type annotation from a function definition node."""
        type_node = func_node.child_by_field_name(
            "return_type"
        ) or func_node.child_by_field_name("type")
        if not type_node:
            return None
        refs = self.resolve_type_texts(
            self._syntax.node_text(type_node), enclosing_func_node=func_node
        )
        return refs[0] if refs else None

    def get_enclosing_function_node(self, node: TSNode) -> TSNode | None:
        """Walk up tree to enclosing function definition."""
        current = node.parent
        fn_types = self._syntax._ctx.lang_cfg.cst.function_scope_types
        while current:
            if current.type in fn_types:
                return current
            current = current.parent
        return None

    def get_typed_parameters(self, func_node: TSNode) -> list[tuple[str, list[str]]]:
        """Collect (param_name, type_refs) for all typed parameters."""
        params = func_node.child_by_field_name("parameters")
        if not params:
            return []
        param_types = self._syntax._ctx.lang_cfg.cst.typed_param_types
        result: list[tuple[str, list[str]]] = []
        for child in params.children:
            if child.type in param_types:
                extracted = self.extract_type_from_typed_param(child)
                if extracted:
                    result.append(extracted)
        return result

    def get_parameter_type_hint(self, func_node: TSNode, param_name: str) -> str | None:
        """Get type hint for a specific parameter by name."""
        for name, refs in self.get_typed_parameters(func_node):
            if name == param_name:
                return refs[0] if refs else None
        return None

    def find_method_in_class(self, class_name: str, method_name: str) -> TSNode | None:
        """Find method node inside a class by simple class name."""
        class_node = self._find_class_node(class_name)
        if not class_node:
            return None
        return self.find_method_in_class_body(class_node, method_name)
