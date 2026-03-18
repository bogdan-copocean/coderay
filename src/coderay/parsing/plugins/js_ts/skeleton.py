"""JS/TS-specific skeleton extractor."""

from __future__ import annotations

import logging

from coderay.parsing.base import BaseTreeSitterParser

logger = logging.getLogger(__name__)

ELLIPSIS = "..."

# JS/TS tree-sitter node types
_IMPORT_TYPES = ("import_statement",)
_FUNCTION_SCOPE_TYPES = (
    "function_declaration",
    "method_definition",
    "arrow_function",
)
_CLASS_SCOPE_TYPES = ("class_declaration",)
_EXTRA_CLASS_LIKE_TYPES = (
    "interface_declaration",
    "type_alias_declaration",
    "type_declaration",
)
_BODY_BLOCK_TYPES = ("statement_block",)
_TOP_LEVEL_EXPR_TYPES = ("expression_statement", "lexical_declaration")
_DOCSTRING_EXPR_TYPE = "expression_statement"


class JsTsSkeleton:
    """Extract skeleton from JS/TS files."""

    def extract(
        self,
        ctx,
        *,
        include_imports: bool = True,
        symbol: str | None = None,
    ) -> str:
        """Return skeleton text (signatures, docstrings, no bodies)."""
        parser = _JsTsSkeletonParser(
            ctx, include_imports=include_imports, symbol=symbol
        )
        try:
            lines = parser.collect_lines()
            return "\n".join(lines)
        except Exception:  # pragma: no cover
            logger.exception("Skeleton extraction failed")
            return ctx.content


class _JsTsSkeletonParser(BaseTreeSitterParser):
    """Tree-sitter skeleton parser for JS/TS."""

    def __init__(
        self,
        context,
        *,
        include_imports: bool = True,
        symbol: str | None = None,
    ) -> None:
        super().__init__(context)
        self._include_imports = include_imports
        self._symbol = symbol

    def collect_lines(self) -> list[str]:
        """Return skeleton lines."""
        tree = self.get_tree()
        lines: list[str] = []
        self._seen: set[int] = set()
        self._dfs(tree.root_node, lines, depth=0)
        return lines

    def _extract_text(self, node) -> str | None:
        """Extract string from docstring-capable node."""
        if node.type != _DOCSTRING_EXPR_TYPE:
            return None
        for sub in node.children:
            if sub.type == "string":
                return self.node_text(sub).strip()
        return None

    def _get_docstring(self, node) -> str | None:
        """Extract docstring from body block."""
        if not hasattr(node, "children"):
            return None
        scope_types = (
            *_FUNCTION_SCOPE_TYPES,
            *_CLASS_SCOPE_TYPES,
            *_EXTRA_CLASS_LIKE_TYPES,
        )
        if node.type in scope_types:
            body = None
            for child in node.children:
                if child.type in _BODY_BLOCK_TYPES:
                    body = child
                    break
            if body is None:
                return None
            for child in body.children:
                if text := self._extract_text(child):
                    return text
        for child in node.children:
            if text := self._extract_text(child):
                return text
        return None

    def _get_signature_line(self, node) -> str:
        """Return text up to colon or brace."""
        text = self.node_text(node)
        for delimiter in (":\n", "{\n", ":\r\n", "{\r\n"):
            idx = text.find(delimiter)
            if idx >= 0:
                return text[: idx + 1]
        first_line = text.split("\n")[0]
        return first_line

    def _node_name(self, node) -> str | None:
        """Extract declared name from node."""
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return self.node_text(name_node).strip()
        return None

    def _matches_symbol(self, node, depth: int) -> bool:
        """Return True if node matches symbol filter."""
        if self._symbol is None:
            return True
        if depth > 0:
            return True
        name = self._node_name(node)
        target = self._symbol.split(".")[0] if "." in self._symbol else self._symbol
        return name == target

    def _dfs(self, node, lines: list[str], depth: int) -> None:
        indent = "    " * depth
        ntype = node.type

        interesting = (
            "module",
            *_IMPORT_TYPES,
            *_FUNCTION_SCOPE_TYPES,
            *_CLASS_SCOPE_TYPES,
            *_EXTRA_CLASS_LIKE_TYPES,
        )

        if node.id in self._seen:
            return

        if ntype not in interesting:
            if depth == 0 and ntype in _TOP_LEVEL_EXPR_TYPES:
                if self._symbol is None:
                    text = self.node_text(node).strip()
                    if text and (
                        text.startswith(('"""', "'''", '"', "'")) or "=" in text
                    ):
                        lines.append(text)
            for child in node.children:
                self._dfs(child, lines, depth)
            return

        if ntype in _IMPORT_TYPES:
            if self._include_imports and self._symbol is None:
                lines.append(indent + self.node_text(node).strip())
            return

        if ntype in _FUNCTION_SCOPE_TYPES:
            if not self._matches_symbol(node, depth):
                self._seen.add(node.id)
                return
            lines.append(indent + self._get_signature_line(node))
            if docstr := self._get_docstring(node):
                lines.append(indent + "    " + docstr)
            lines.append(indent + "    " + ELLIPSIS)
            self._seen.add(node.id)
            return

        if ntype in (*_CLASS_SCOPE_TYPES, *_EXTRA_CLASS_LIKE_TYPES):
            if not self._matches_symbol(node, depth):
                self._seen.add(node.id)
                return
            lines.append(indent + self._get_signature_line(node))
            if docstr := self._get_docstring(node):
                lines.append(indent + "    " + docstr)
            self._seen.add(node.id)
            for child in node.children:
                self._dfs(child, lines, depth + 1)
            return

        self._seen.add(node.id)
        for child in node.children:
            self._dfs(child, lines, depth)
