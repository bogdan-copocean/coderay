"""Call and decorator lowering (CALLS facts and callee resolution)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coderay.graph._utils import _BASE_CLASS_NODE_TYPES
from coderay.graph.facts import CallsEdge
from coderay.parsing.base import TSNode

if TYPE_CHECKING:
    from coderay.graph.facts import Fact
    from coderay.graph.file_context import FileContext
    from coderay.parsing.base import ParserContext


class CallMixin:
    """Handle calls: CALLS facts, callee resolution, and instantiation tracking."""

    file_path: str
    _module_id: str
    _facts: set[Fact]
    _file_ctx: FileContext
    _ctx: ParserContext
    _supported_extensions: set[str]

    if TYPE_CHECKING:

        def node_text(self, node: Any) -> str: ...
        def _find_class_node(self, class_name: str) -> Any | None: ...
        def _get_enclosing_function_node(self, node: Any) -> Any | None: ...
        def _find_enclosing_class_from_node(self, node: Any) -> str | None: ...
        def _get_base_classes_from_arg_list(self, node: Any) -> list[str]: ...

    def _caller_id_from_scope(self, scope_stack: list[str]) -> str:
        """Return caller node ID for scope."""
        if scope_stack:
            return f"{self.file_path}::{'.'.join(scope_stack)}"
        return self._module_id

    def _add_call_edges(
        self, caller_id: str, raw: str, callee_targets: list[str]
    ) -> None:
        """Append CALLS facts for resolved targets."""
        for callee_name in callee_targets:
            if callee_name:
                self._facts.add(CallsEdge(source_id=caller_id, target=callee_name))

    def _handle_call(self, node: TSNode, *, scope_stack: list[str]) -> None:
        # foo()  |  self.method()  |  super().method()  |  a.b.c()
        """Create CALLS facts to resolved callee."""
        caller_id = self._caller_id_from_scope(scope_stack)

        callee_node = node.child_by_field_name("function")
        if callee_node is None:
            return
        raw_callee = self.node_text(callee_node)
        if not raw_callee:
            return

        callee_targets = self._resolve_callee_targets(raw_callee, scope_stack)
        self._add_call_edges(caller_id, raw_callee, callee_targets)
        self._maybe_track_instantiation(node, raw_callee)

    def _resolve_callee_targets(self, raw: str, scope_stack: list[str]) -> list[str]:
        """Resolve callee to qualified targets (super -> self -> simple -> chain).

        Resolution priority: super() calls first (most specific), then self/this
        member access, then bare names, then dotted chains. First match wins.
        """
        graph = self._ctx.lang_cfg.graph
        result = self._resolve_super_targets(raw, scope_stack, graph.super_prefixes)
        if result is not None:
            return result
        result = self._resolve_self_targets(raw, scope_stack, graph.self_prefix)
        if result is not None:
            return result
        parts = raw.split(".")
        if len(parts) == 1:
            return self._resolve_simple_name_targets(raw)
        return self._resolve_chain_targets(raw)

    def _resolve_super_targets(
        self, raw: str, scope_stack: list[str], super_prefixes: tuple[str, ...]
    ) -> list[str] | None:
        # super().method()  ->  [parent_class.method]
        """Resolve super().method to parent class method."""
        for prefix in super_prefixes:
            if raw.startswith(prefix):
                method = raw[len(prefix) :]
                target = self._resolve_super_call(scope_stack, method)
                return [target] if target else [method]
        return None

    def _resolve_self_targets(
        self, raw: str, scope_stack: list[str], self_prefix: str
    ) -> list[str] | None:
        # self.method()  ->  [file::Class.method]
        """Resolve self.method via instance/class attrs."""
        if not self_prefix or not raw.startswith(self_prefix):
            return None
        # "self.repo.save" -> suffix="repo.save", parts=["repo","save"], method="save"
        suffix = raw.split(".", 1)[1]
        parts = suffix.split(".")
        method = parts[-1]

        # Direct method: self.method() -> file::EnclosingClass.method
        if len(parts) == 1:
            class_qualified = self._find_enclosing_class(scope_stack)
            if class_qualified:
                return [f"{self.file_path}::{class_qualified}.{method}"]

        # Chained: self.repo.save() -> look up self.repo's type, then .save
        instance_key = self_prefix + ".".join(parts[:-1])
        class_ref = self._file_ctx.resolve_instance(instance_key)
        if not class_ref:
            # Fall back to class attribute type (e.g. from @property return type)
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
        # foo()  ->  [resolved_foo] or [instance_class.__call__]
        """Resolve simple name via alias/import/instance."""
        name = raw
        instance_class = self._file_ctx.resolve_instance(name)
        if instance_class:
            return [f"{instance_class}.__call__"]
        resolved = self._file_ctx.resolve(name)
        return [resolved] if resolved else [name]

    def _resolve_chain_targets(self, raw: str) -> list[str]:
        # a.b.method()  ->  resolve a, follow chain, append method
        """Resolve obj.attr.method() chains."""
        parts = raw.split(".")
        obj_name = parts[0]
        method_name = parts[-1]

        # Long chains (a.b.c()): walk class attributes to resolve intermediate types
        if len(parts) > 2:
            chain = ".".join(parts[:-1])
            chain_refs = self._file_ctx.resolve_chain(chain)
            if chain_refs:
                return [f"{ref}.{method_name}" for ref in chain_refs]

        # Short chain (obj.method()): look up obj as a known instance
        method_targets = self._file_ctx.resolve_method_calls(obj_name, method_name)
        if method_targets:
            return method_targets

        # obj is an imported module/alias — qualify with :: or . depending on type
        obj_resolved = self._file_ctx.resolve(obj_name)
        if obj_resolved:
            tail = ".".join(parts[1:])
            # If obj resolves to a file path (has .py/.ts ext), use :: separator
            _, ext = obj_resolved.rsplit(".", 1) if "." in obj_resolved else ("", "")
            if ext and f".{ext}" in self._supported_extensions:
                return [f"{obj_resolved}::{tail}"]
            return [f"{obj_resolved}.{tail}"]

        # Unresolvable — keep bare method name as phantom target
        return [method_name]

    def _resolve_super_call(self, scope_stack: list[str], method: str) -> str | None:
        """Resolve super().method() to parent class method."""
        class_qualified = self._find_enclosing_class(scope_stack)
        if not class_qualified:
            return None
        base_name = self._get_first_base_class(class_qualified)
        if not base_name:
            return None
        base_resolved = self._file_ctx.resolve(base_name)
        if not base_resolved:
            base_resolved = f"{self.file_path}::{base_name}"
        return f"{base_resolved}.{method}"

    def _get_first_base_class(self, class_qualified: str) -> str | None:
        """Return first base class name for class (uses shared _find_class_node)."""
        target_class = class_qualified.split(".")[-1]
        class_node = self._find_class_node(target_class)
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
        # x = SomeClass()  ->  register x as instance of SomeClass
        """Track constructor call as instance for later method resolution."""
        # Only relevant if the call is the RHS of an assignment
        parent = call_node.parent
        if parent is None or parent.type not in self._ctx.lang_cfg.cst.assignment_types:
            return

        # Get the LHS variable being assigned to
        lhs = (
            parent.child_by_field_name("name")
            or parent.child_by_field_name("left")
            or (parent.children[0] if parent.children else None)
        )
        if lhs is None:
            return

        self_prefix = self._ctx.lang_cfg.graph.self_prefix
        if lhs.type == "identifier":
            var_name = self.node_text(lhs)
        elif lhs.type == "attribute":
            # self.x = SomeClass() — only track self-prefixed attributes
            var_name = self.node_text(lhs)
            if not self_prefix or not var_name.startswith(self_prefix):
                return
        else:
            return

        # Already registered (e.g. from return-type annotation in assignment handler)
        if self._file_ctx.resolve_instance(var_name):
            return

        # Use the last segment: "mod.SomeClass" -> "SomeClass"
        callee_base = raw_callee.rsplit(".", 1)[-1]
        if not callee_base:
            return

        # Heuristic: treat as constructor if name is a known class or starts uppercase
        resolved = self._file_ctx.resolve(callee_base)
        is_known_class = self._file_ctx.is_class(callee_base)
        is_likely_class = bool(callee_base[0].isupper() and resolved is not None)

        if is_known_class or is_likely_class:
            self._file_ctx.register_instance(var_name, resolved or callee_base)
            # If assigning to self.attr, also register as a class-level attribute
            if self_prefix and var_name.startswith(self_prefix):
                func_node = self._get_enclosing_function_node(call_node)
                if func_node:
                    class_qualified = self._find_enclosing_class_from_node(func_node)
                    if class_qualified:
                        attr_name = var_name.split(".", 1)[1].split(".")[0]
                        self._file_ctx.register_class_attribute(
                            class_qualified, attr_name, resolved or callee_base
                        )

    def _handle_decorator(self, node: TSNode, *, scope_stack: list[str]) -> None:
        # @trace \n def foo(): ...  ->  CALLS from foo to trace
        # @app.route("/") \n def index(): ... -> CALLS from index to app.route
        """Create CALLS facts for decorator targets (bare and dotted)."""
        # Collect all stacked decorators and the name of the decorated symbol
        decorators: list[str] = []
        decorated_name: str | None = None

        for child in node.named_children:
            if child.type == "decorator":
                # Extract decorator name: identifier, attribute, or call expression
                deco_text = self._extract_decorator_name(child)
                if deco_text:
                    decorators.append(deco_text)
            elif child.type in ("function_definition", "class_definition"):
                for cchild in child.named_children:
                    if cchild.type == "identifier":
                        decorated_name = self.node_text(cchild).strip()
                        break

        if not decorators:
            return

        # Caller is the decorated symbol (foo calls trace, not the outer scope).
        caller_scope = scope_stack + [decorated_name] if decorated_name else scope_stack
        caller_id = self._caller_id_from_scope(caller_scope)
        # Resolve each decorator in the *outer* scope (decorators are defined outside)
        for decorator in decorators:
            callee_targets = self._resolve_callee_targets(decorator, scope_stack)
            self._add_call_edges(caller_id, decorator, callee_targets)

    def _extract_decorator_name(self, decorator_node: TSNode) -> str | None:
        """Extract name from decorator node (handles bare, dotted, and call forms)."""
        for child in decorator_node.named_children:
            # @decorator
            if child.type == "identifier":
                return self.node_text(child).strip() or None
            # @mod.decorator or @app.route
            if child.type in ("attribute", "member_expression"):
                return self.node_text(child).strip() or None
            # @app.route("/path") — call expression wrapping the decorator
            if child.type in self._ctx.lang_cfg.cst.call_types:
                callee = child.child_by_field_name("function")
                if callee:
                    return self.node_text(callee).strip() or None
        return None
