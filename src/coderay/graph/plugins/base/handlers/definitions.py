"""Class and function definition lowering (symbols and inheritance)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coderay.core.models import NodeKind
from coderay.graph._utils import _BASE_CLASS_NODE_TYPES
from coderay.graph.facts import InheritsEdge, SymbolDefinition
from coderay.parsing.base import TSNode

if TYPE_CHECKING:
    from coderay.graph.facts import Fact
    from coderay.graph.file_context import FileContext


class DefinitionMixin:
    """Handle class/function definitions: symbol facts and INHERITS edges."""

    file_path: str
    _module_id: str
    _facts: set[Fact]
    _file_ctx: FileContext

    if TYPE_CHECKING:

        def identifier_from_node(self, node: Any, parent: Any = ...) -> str: ...
        def node_text(self, node: Any) -> str: ...
        def _dfs(self, node: Any, *, scope_stack: list[str]) -> None: ...

    def _handle_function_def(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Record function symbol; recurse into body."""
        self._handle_definition(node, scope_stack=scope_stack, kind=NodeKind.FUNCTION)

    def _handle_class_def(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Record class symbol and INHERITS edges; recurse into body."""
        self._handle_definition(node, scope_stack=scope_stack, kind=NodeKind.CLASS)

    def _handle_definition(
        self, node: TSNode, *, scope_stack: list[str], kind: NodeKind
    ) -> None:
        # def foo():  |  class Foo(Base):  |  function foo() {}
        """Shared handler for function and class definitions."""
        name = self.identifier_from_node(node)
        if not name:
            return

        # Build qualified name: e.g. scope=["Svc"], name="run" -> "Svc.run"
        qualified = ".".join([*scope_stack, name])
        # Definer is the enclosing scope (module or class that "owns" this symbol)
        definer = self._module_id
        if scope_stack:
            definer = f"{self.file_path}::{'.'.join(scope_stack)}"
        node_id = f"{self.file_path}::{qualified}"

        self._facts.add(
            SymbolDefinition(
                file_path=self.file_path,
                scope_stack=tuple(scope_stack),
                name=name,
                kind=kind,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                definer_id=definer,
            )
        )

        is_class = kind == NodeKind.CLASS

        if is_class:
            # Emit INHERITS edges for each base class in argument_list / extends_clause
            for child in node.children:
                if child.type not in _BASE_CLASS_NODE_TYPES:
                    continue
                for base_name in self._get_base_classes_from_arg_list(child):
                    resolved = self._resolve_base_class(base_name)
                    self._facts.add(InheritsEdge(source_id=node_id, target=resolved))
            # Register as class so _find_enclosing_class / is_class can find it
            self._file_ctx.register_definition(name, node_id, is_class=True)
        else:
            # Top-level: register by simple name; nested: register by qualified name
            if not scope_stack:
                self._file_ctx.register_definition(name, node_id)
            else:
                self._file_ctx.register_definition(qualified, node_id)
            # Language hook: e.g. Python registers typed param instances here
            self._after_function_definition_registered(node, scope_stack=scope_stack)

        # Recurse into body with the symbol pushed onto the scope stack
        new_scope = [*scope_stack, name]
        for child in node.children:
            self._dfs(child, scope_stack=new_scope)

    def _after_function_definition_registered(
        self, node: TSNode, *, scope_stack: list[str]
    ) -> None:
        """Hook after function symbol is registered; override per language."""
        del node, scope_stack

    def _get_base_classes_from_arg_list(self, arg_list_node: TSNode) -> list[str]:
        # class Foo(Base, Mixin):  ->  ["Base", "Mixin"]
        # class Foo(Base[T]): -> ["Base"] (generic_type; name before [...])
        """Extract base class names from argument_list or extends_clause."""
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
            elif arg.type in ("generic_type", "subscript"):
                # Base[T] / Base[User] — first named child is the class name
                if arg.named_children:
                    name = self.node_text(arg.named_children[0])
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
