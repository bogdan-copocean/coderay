"""Python CST -> graph facts."""

from __future__ import annotations

from coderay.graph.plugins.base.extractor import BaseGraphExtractor
from coderay.graph.plugins.python.import_handler import PythonImportHandler
from coderay.parsing.base import ParserContext, TSNode


class PythonGraphExtractor(BaseGraphExtractor):
    """Lower Python tree-sitter CST to graph facts."""

    def __init__(
        self,
        context: ParserContext,
        *,
        module_index: dict[str, str] | None = None,
    ) -> None:
        """Initialize Python extractor."""
        super().__init__(context, module_index=module_index)
        self._import_handler = PythonImportHandler()

    # ------------------------------------------------------------------
    # Type resolution overrides (Python CST shapes)
    # ------------------------------------------------------------------

    def _find_method_in_class_body(
        self, class_node: TSNode, method_name: str
    ) -> TSNode | None:
        """Find method in Python class body (handles decorated_definition)."""
        body_types = self._ctx.lang_cfg.cst.class_body_types
        for child in class_node.children:
            if child.type not in body_types:
                continue
            for stmt in child.children:
                fn = self._unwrap_decorated(stmt)
                if fn is None:
                    continue
                fn_name = self.node_text(fn.child_by_field_name("name"))
                if fn_name == method_name:
                    return fn
        return None

    def _find_top_level_function(self, func_name: str) -> TSNode | None:
        """Find top-level function_definition by name."""

        def search(n: TSNode) -> TSNode | None:
            if n.type == "function_definition":
                name_node = n.child_by_field_name("name")
                if name_node and self.node_text(name_node) == func_name:
                    return n
            for c in n.children:
                found = search(c)
                if found:
                    return found
            return None

        return search(self.get_tree().root_node)

    def _unwrap_decorated(self, stmt: TSNode) -> TSNode | None:
        """Return inner function_definition from decorated_definition."""
        if stmt.type == "function_definition":
            return stmt
        if stmt.type == "decorated_definition":
            for c in stmt.children:
                if c.type == "function_definition":
                    return c
        return None

    def _extract_tuple_type_args(self, type_node: TSNode) -> list[str]:
        # def func() -> tuple[A, B]:  ->  ["file::A", "file::B"]
        """Extract type args from tuple[X, Y, ...] annotation."""
        # Unwrap CST wrapper: "type" node contains the actual generic_type
        if type_node.type == "type" and type_node.named_children:
            type_node = type_node.named_children[0]
        # Must be generic_type with at least 2 children: base name + type params
        if type_node.type != "generic_type":
            return []
        children = type_node.named_children
        if len(children) < 2:
            return []
        # Only handle tuple[...], case-insensitive
        base_name = self.node_text(children[0])
        if base_name.lower() != "tuple":
            return []
        # Resolve each type parameter individually
        type_param_node = children[1]
        result: list[str] = []
        for type_child in type_param_node.named_children:
            if type_child.type == "type":
                refs = self._resolve_type_texts(self.node_text(type_child))
                result.extend(refs)
        return result

    # ------------------------------------------------------------------
    # Definition override (typed params + @property)
    # ------------------------------------------------------------------

    def _after_function_definition_registered(
        self, node: TSNode, *, scope_stack: list[str]
    ) -> None:
        # def __init__(self, repo: UserRepository):  ->  register repo as instance
        # @property \n def name(self) -> str:  ->  register class attribute
        """Register typed-parameter instances and @property class attributes."""
        for param_name, type_refs in self._get_typed_parameters(node):
            if len(type_refs) == 1:
                self._file_ctx.register_instance(param_name, type_refs[0])
            else:
                self._file_ctx.register_instance_union(param_name, type_refs)

        if self._is_property(node) and scope_stack:
            name = self.identifier_from_node(node)
            if not name:
                return
            class_qualified = ".".join(scope_stack)
            return_type = self._get_return_type_from_func_node(node)
            if return_type:
                self._file_ctx.register_class_attribute(
                    class_qualified, name, return_type
                )

    def _is_property(self, func_node: TSNode) -> bool:
        """Return True if function has @property decorator."""
        parent = func_node.parent
        if parent is None or parent.type != "decorated_definition":
            return False
        for child in parent.children:
            if child.type == "decorator":
                text = self.node_text(child).strip()
                if text.endswith("property"):
                    return True
        return False

    # ------------------------------------------------------------------
    # Assignment overrides (tuple unpack, partial, with/as)
    # ------------------------------------------------------------------

    def _handle_assignment(self, node: TSNode, *, scope_stack: list[str]) -> None:
        # a, b = get_pair()  ->  unpack from tuple[A, B] return type
        """Handle tuple unpacking; delegate simple assignments to base."""
        lhs, rhs = self._get_assignment_sides(node)
        if lhs is None or rhs is None:
            return

        if lhs.type in ("pattern_list", "tuple_pattern", "list_pattern"):
            self._handle_tuple_unpacking(lhs, rhs)
            return

        super()._handle_assignment(node, scope_stack=scope_stack)

    def _register_assignment_from_call(
        self,
        lhs_name: str,
        rhs: TSNode,
        node: TSNode,
        scope_stack: list[str],
    ) -> None:
        # handler = partial(process, config)  ->  alias handler to process
        """Resolve partial() first-arg alias; otherwise delegate to base."""
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self.node_text(callee_node).strip()
        if not callee_name:
            return
        if callee_name == "partial" or callee_name.endswith(".partial"):
            first_arg = self._get_first_call_arg(rhs)
            if first_arg:
                resolved = self._file_ctx.resolve(first_arg)
                if resolved:
                    self._file_ctx.register_alias(lhs_name, resolved)
            return
        super()._register_assignment_from_call(lhs_name, rhs, node, scope_stack)

    def _handle_with_statement(self, node: TSNode, *, scope_stack: list[str]) -> None:
        # with open(path) as f:  ->  register f from __enter__ return type
        """Register with-as targets from context manager __enter__ return type."""
        del scope_stack
        for child in node.children:
            if child.type in ("with_clause", "with_clauses"):
                for item in child.children:
                    if item.type == "with_item":
                        self._process_with_item(item)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_with_item(self, item: TSNode) -> None:
        """Register as-target with __enter__ return type."""
        # CST shape: with_item has a "value" child that is either:
        #   as_pattern: "Pool() as conn" — alias is "conn", call is Pool()
        #   direct call: bare "Pool()" without as binding
        value = item.child_by_field_name("value")
        if not value:
            return
        if value.type == "as_pattern":
            # "Pool() as conn" — extract the alias ("conn") and call node (Pool())
            target_node = value.child_by_field_name("alias")
            call_node = next(
                (
                    c
                    for c in value.named_children
                    if c.type in self._ctx.lang_cfg.cst.call_types
                ),
                None,
            )
        else:
            target_node = value if value.type == "as_pattern_target" else None
            call_node = (
                value if value.type in self._ctx.lang_cfg.cst.call_types else None
            )
        if not call_node or not target_node:
            return
        var_name = self.node_text(target_node)
        if not var_name or var_name == "_":
            return
        # Look up the context manager's __enter__ return type to type the variable
        callee_node = call_node.child_by_field_name("function")
        cm_name = self.node_text(callee_node).strip() if callee_node else ""
        if not cm_name:
            return
        enter_return = self._get_function_return_type(f"{cm_name}.__enter__")
        if enter_return:
            self._file_ctx.register_instance(var_name, enter_return)

    def _handle_tuple_unpacking(self, lhs: TSNode, rhs: TSNode) -> None:
        # a, b = get_pair()  ->  register a, b from tuple[A, B] return type
        """Track tuple unpacking from call return type annotation."""
        # Collect all non-underscore identifier targets from the LHS pattern
        identifiers: list[str] = []
        for child in lhs.children:
            if child.type == "identifier":
                name = self.node_text(child)
                if name and name != "_":
                    identifiers.append(name)
        if not identifiers:
            return

        # Only handle unpacking from function calls (not literals or other exprs)
        if rhs.type not in self._ctx.lang_cfg.cst.call_types:
            return
        callee_node = rhs.child_by_field_name("function")
        if not callee_node:
            return
        callee_name = self.node_text(callee_node).strip()
        if not callee_name:
            return

        # Find the function definition to inspect its return type annotation
        func_node = (
            self._find_method_in_class(*callee_name.split(".", 1))
            if "." in callee_name
            else self._find_top_level_function(callee_name)
        )
        if not func_node:
            return
        type_node = func_node.child_by_field_name(
            "return_type"
        ) or func_node.child_by_field_name("type")
        if not type_node:
            return

        # Match tuple[A, B, ...] type args positionally to LHS identifiers
        type_args = self._extract_tuple_type_args(type_node)
        for i, name in enumerate(identifiers):
            if i < len(type_args):
                self._file_ctx.register_alias(name, type_args[i])

    def _get_first_call_arg(self, call_node: TSNode) -> str | None:
        """Extract first positional argument identifier from call."""
        arg_list = call_node.child_by_field_name("arguments") or next(
            (c for c in call_node.children if c.type == "argument_list"), None
        )
        if not arg_list:
            return None
        for child in arg_list.named_children:
            if child.type in ("identifier", "dotted_name", "attribute"):
                return self.node_text(child)
        return None
