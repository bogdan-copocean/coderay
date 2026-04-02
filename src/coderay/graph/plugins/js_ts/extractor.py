"""JavaScript/TypeScript CST -> graph facts."""

from __future__ import annotations

from coderay.graph.plugins.base.extractor import BaseGraphExtractor
from coderay.graph.plugins.js_ts.import_handler import JsTsImportHandler
from coderay.parsing.base import ParserContext, TSNode


class JsTsGraphExtractor(BaseGraphExtractor):
    """Lower JS/TS tree-sitter CST to graph facts."""

    def __init__(
        self,
        context: ParserContext,
        *,
        module_index: dict[str, str] | None = None,
    ) -> None:
        """Initialize JS/TS extractor."""
        super().__init__(context, module_index=module_index)
        self._import_handler = JsTsImportHandler()

    # ------------------------------------------------------------------
    # Type resolution overrides (JS/TS CST shapes)
    # ------------------------------------------------------------------

    def _find_method_in_class_body(
        self, class_node: TSNode, method_name: str
    ) -> TSNode | None:
        # class Foo { bar() {} }  ->  find method_definition "bar"
        """Find method_definition in JS/TS class body."""
        body_types = self._ctx.lang_cfg.cst.class_body_types
        for child in class_node.children:
            if child.type not in body_types:
                continue
            for stmt in child.children:
                if stmt.type != "method_definition":
                    continue
                name_node = stmt.child_by_field_name("name")
                if name_node and self.node_text(name_node) == method_name:
                    return stmt
        return None

    def _find_top_level_function(self, func_name: str) -> TSNode | None:
        # function foo() {}  |  const foo = () => {}
        """Find top-level function or arrow function variable by name."""

        def search(n: TSNode) -> TSNode | None:
            if n.type in ("function_declaration", "function_definition"):
                name_node = n.child_by_field_name("name")
                if name_node and self.node_text(name_node) == func_name:
                    return n
            if n.type == "variable_declarator":
                name_node = n.child_by_field_name("name")
                if name_node and self.node_text(name_node) == func_name:
                    value = n.child_by_field_name("value")
                    if value and value.type == "arrow_function":
                        return value
            for c in n.children:
                found = search(c)
                if found:
                    return found
            return None

        return search(self.get_tree().root_node)
