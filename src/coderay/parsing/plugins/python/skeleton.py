"""Python-specific skeleton extractor."""

from __future__ import annotations

import logging

from coderay.parsing.base import BaseTreeSitterParser

logger = logging.getLogger(__name__)

ELLIPSIS = "..."

# Python tree-sitter node types
_IMPORT_TYPES = ("import_statement", "import_from_statement", "future_import_statement")
_FUNCTION_SCOPE_TYPES = ("function_definition",)
_CLASS_SCOPE_TYPES = ("class_definition",)
_DECORATOR_SCOPE_TYPES = ("decorated_definition",)
_BODY_BLOCK_TYPES = ("block",)
_DOCSTRING_EXPR_TYPE = "expression_statement"
_TOP_LEVEL_EXPR_TYPES = ("expression_statement",)


class PythonSkeleton:
    """Extract skeleton from Python files."""

    def extract(
        self,
        ctx,
        *,
        include_imports: bool = True,
        symbol: str | None = None,
    ) -> str:
        """Return skeleton text (signatures, docstrings, no bodies)."""
        parser = _PythonSkeletonParser(
            ctx, include_imports=include_imports, symbol=symbol
        )
        try:
            lines = parser.collect_lines()
            if symbol and not lines:
                return _symbol_not_found_hint(ctx, symbol)
            return "\n".join(lines)
        except Exception:  # pragma: no cover
            logger.exception("Skeleton extraction failed")
            return ctx.content


def _symbol_not_found_hint(ctx, symbol: str) -> str:
    """Return a diagnostic listing the top-level symbols in *ctx*."""
    helper = BaseTreeSitterParser(ctx)
    tree = helper.get_tree()
    names: list[str] = []
    for child in tree.root_node.children:
        node = child
        if node.type in _DECORATOR_SCOPE_TYPES:
            for inner in node.named_children:
                if inner.type in (*_FUNCTION_SCOPE_TYPES, *_CLASS_SCOPE_TYPES):
                    node = inner
                    break
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            raw = name_node.text
            names.append(raw.decode() if isinstance(raw, bytes) else raw)
    available = ", ".join(sorted(set(names))) if names else "(none)"
    return f"# Symbol '{symbol}' not found. Available symbols: {available}"


class _PythonSkeletonParser(BaseTreeSitterParser):
    """Tree-sitter skeleton parser for Python."""

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
        """Extract string from docstring-capable node (expression_statement)."""
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
        scope_types = (*_FUNCTION_SCOPE_TYPES, *_CLASS_SCOPE_TYPES)
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
        """Return True if node matches the symbol filter."""
        if self._symbol is None:
            return True
        # "Class.method" → depth 0 matches "Class", depth 1 matches "method"
        # "Class" alone → depth 0 matches "Class", depth 1 matches everything
        parts = self._symbol.split(".", 1)
        class_part = parts[0]
        method_part = parts[1] if len(parts) > 1 else None
        if depth == 0:
            return self._node_name(node) == class_part
        if method_part is not None and depth == 1:
            return self._node_name(node) == method_part
        return method_part is None

    def _decorated_inner(self, node):
        """Return inner class/function from decorated node."""
        for child in node.named_children:
            if child.type in (*_FUNCTION_SCOPE_TYPES, *_CLASS_SCOPE_TYPES):
                return child
        return None

    def _dfs(self, node, lines: list[str], depth: int) -> None:
        indent = "    " * depth
        ntype = node.type

        interesting = (
            "module",
            *_IMPORT_TYPES,
            *_FUNCTION_SCOPE_TYPES,
            *_CLASS_SCOPE_TYPES,
            *_DECORATOR_SCOPE_TYPES,
        )

        if node.id in self._seen:
            return

        # Uninteresting nodes: pass through, but capture top-level constants/docstrings
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

        # Decorated nodes: emit decorator lines, then recurse into the inner def/class
        if ntype in _DECORATOR_SCOPE_TYPES:
            inner = self._decorated_inner(node)
            if inner is not None and not self._matches_symbol(inner, depth):
                self._seen.add(node.id)
                return
            for child in node.named_children:
                if child.type == "decorator":
                    lines.append(indent + self.node_text(child).strip())
                    self._seen.add(child.id)
                    continue
                if child.type in (*_FUNCTION_SCOPE_TYPES, *_CLASS_SCOPE_TYPES):
                    self._dfs(child, lines, depth)
                    break
            self._seen.add(node.id)
            return

        # Functions: signature + docstring + ellipsis, no body traversal
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

        # Classes: signature + docstring, then recurse into body at depth+1
        if ntype in _CLASS_SCOPE_TYPES:
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
