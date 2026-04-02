"""Type annotation resolution (language-agnostic core)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coderay.parsing.base import TSNode

if TYPE_CHECKING:
    from coderay.graph.file_context import FileContext
    from coderay.parsing.base import ParserContext


class TypeResolutionMixin:
    """Resolve type annotations via FileContext; subclasses supply CST finders."""

    file_path: str
    _file_ctx: FileContext
    _ctx: ParserContext

    if TYPE_CHECKING:

        def node_text(self, node: Any) -> str: ...
        def _find_class_node(self, class_name: str) -> Any | None: ...

    def _resolve_type_text(self, type_text: str | None) -> str | None:
        """Resolve annotation to a single qualified class ref."""
        refs = self._resolve_type_texts(type_text)
        return refs[0] if refs else None

    def _resolve_type_texts(
        self, type_text: str | None, *, enclosing_func_node: TSNode | None = None
    ) -> list[str]:
        # "int | MyClass" -> ["file::MyClass"]
        # "Self" -> ["file::EnclosingClass"]
        # "mod.MyClass" -> ["resolved_mod::MyClass"]
        """Resolve union/qualified annotation to list of qualified class refs."""
        if not type_text:
            return []
        text = type_text.strip()
        # Strip forward-reference quotes (both single and double)
        if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
            text = text[1:-1]
        # PEP 673 Self — resolve to the enclosing class
        if text == "Self" and enclosing_func_node:
            class_qualified = self._find_enclosing_class_from_node(enclosing_func_node)
            if class_qualified:
                return [f"{self.file_path}::{class_qualified}"]
            return []
        # Split union "A | B" and resolve each part independently
        parts = [p.strip() for p in text.split("|")]
        result: list[str] = []
        for part in parts:
            if not part:
                continue
            # Skip non-class types (None, primitives starting lowercase)
            if part in ("None", "NoneType"):
                continue
            # Dotted: "mod.MyClass" — resolve the alias prefix, keep the class name
            if "." in part and not part[0].isupper():
                alias, _, attr = part.partition(".")
                if attr and attr[0].isupper():
                    resolved_alias = self._file_ctx.resolve(alias)
                    if resolved_alias:
                        result.append(f"{resolved_alias}::{attr}")
                continue
            # Lowercase names (int, str, ...) are never class refs
            if not part[0].isupper():
                continue
            # Simple name: look up in file context, fall back to file-local
            resolved = self._file_ctx.resolve(part)
            result.append(resolved or f"{self.file_path}::{part}")
        return result

    def _find_enclosing_class_from_node(self, node: TSNode) -> str | None:
        """Walk up tree to find innermost enclosing class qualified name."""
        current = node.parent
        # Collect class names bottom-up (inner -> outer), then reverse
        class_names: list[str] = []
        while current:
            if current.type in self._ctx.lang_cfg.cst.class_scope_types:
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
        # Reverse to get outer-first: Outer.Inner
        class_names.reverse()
        return ".".join(class_names)

    def _extract_type_from_typed_param(
        self, param_node: TSNode
    ) -> tuple[str, list[str]] | None:
        # def func(x: MyClass) -> extract ("x", ["file::MyClass"])
        """Extract (param_name, type_refs) from a typed parameter node."""
        # Get parameter name — grammar field "name" or first child as fallback
        name_node = param_node.child_by_field_name("name") or (
            param_node.children[0] if param_node.children else None
        )
        if not name_node:
            return None
        pname = self.node_text(name_node)
        # Get type annotation — grammar field "type" or scan children for a "type" node
        type_node = param_node.child_by_field_name("type")
        if type_node is None:
            for c in param_node.children:
                if c.type == "type":
                    type_node = c
                    break
        if not type_node:
            return None
        # Enclosing function is parent.parent (param -> parameters -> function_def)
        # Needed for resolving "Self" in type annotations
        enclosing = None
        parent = param_node.parent
        if parent and parent.parent:
            enclosing = parent.parent
        type_refs = self._resolve_type_texts(
            self.node_text(type_node), enclosing_func_node=enclosing
        )
        return (pname, type_refs) if type_refs else None

    def _get_function_return_type(self, callee_name: str) -> str | None:
        """Resolve function/method return type from its annotation."""
        if "." in callee_name:
            class_name, method_name = callee_name.split(".", 1)
            func_node = self._find_method_in_class(class_name, method_name)
        else:
            func_node = self._find_top_level_function(callee_name)
        return self._get_return_type_from_func_node(func_node) if func_node else None

    def _get_return_type_from_func_node(self, func_node: TSNode) -> str | None:
        # def func() -> MyClass:  ->  "file::MyClass"
        """Extract return type annotation from function definition node."""
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
            if current.type in self._ctx.lang_cfg.cst.function_scope_types:
                return current
            current = current.parent
        return None

    def _get_typed_parameters(self, func_node: TSNode) -> list[tuple[str, list[str]]]:
        # def func(x: MyClass, y: Other) -> [("x", [...]), ("y", [...])]
        """Collect (param_name, type_refs) for all typed parameters."""
        params = func_node.child_by_field_name("parameters")
        if not params:
            return []
        param_types = self._ctx.lang_cfg.cst.typed_param_types
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
        """Get type hint for a specific parameter by name."""
        for name, refs in self._get_typed_parameters(func_node):
            if name == param_name:
                return refs[0] if refs else None
        return None

    # ------------------------------------------------------------------
    # Language hooks — override in subclass
    # ------------------------------------------------------------------

    def _find_method_in_class(self, class_name: str, method_name: str) -> TSNode | None:
        """Find method node inside a class; delegates to _find_method_in_class_body."""
        class_node = self._find_class_node(class_name)
        if not class_node:
            return None
        return self._find_method_in_class_body(class_node, method_name)

    def _find_method_in_class_body(
        self, class_node: TSNode, method_name: str
    ) -> TSNode | None:
        """Find method in class body — override per language for CST shape."""
        return None

    def _find_top_level_function(self, func_name: str) -> TSNode | None:
        """Find top-level function by name — override per language."""
        return None
