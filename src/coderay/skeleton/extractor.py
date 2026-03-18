from __future__ import annotations

import logging
from pathlib import Path

from coderay.parsing.base import BaseTreeSitterParser, parse_file

logger = logging.getLogger(__name__)

ELLIPSIS = "..."


def extract_skeleton(
    path: str | Path,
    content: str,
    *,
    include_imports: bool = False,
    symbol: str | None = None,
) -> str:
    """Extract skeleton (signatures, no bodies).

    Args:
        path: File path for language detection.
        content: Full file content.
        include_imports: Include import statements when True.
        symbol: Optional; only return this symbol's skeleton.
    """
    ctx = parse_file(path, content)
    if ctx is None:
        return content

    parser = SkeletonTreeSitterParser(
        ctx, include_imports=include_imports, symbol=symbol
    )
    try:
        lines = parser.collect_lines()
    except Exception:  # pragma: no cover - defensive fallback
        logger.exception("Skeleton extraction failed")
        return content
    return "\n".join(lines)


class SkeletonTreeSitterParser(BaseTreeSitterParser):
    """Tree-sitter skeleton extractor."""

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
        """Return skeleton as list of lines."""
        tree = self.get_tree()
        lines: list[str] = []
        self._seen = set()
        self._dfs(tree.root_node, lines, depth=0)
        return lines

    def _extract_text(self, node) -> str | None:
        """Extract string from expression_statement; None otherwise."""
        if node.type == "expression_statement":
            for sub in node.children:
                if sub.type == "string":
                    return self.node_text(sub).strip()
        return None

    def _get_docstring(self, node) -> str | None:
        """Extract docstring from body block; None if absent."""
        if not hasattr(node, "children"):
            return None

        # For class/function level docstring
        if node.type in ("function_definition", "class_definition"):
            body = None
            for child in node.children:
                if child.type in ("block", "statement_block"):
                    body = child
                    break

            if body is None:
                return None

            for child in body.children:
                if text := self._extract_text(child):
                    return text

        # Module-level or other: first expression_statement with string
        for child in node.children:
            if text := self._extract_text(child):
                return text
        return None

    def _get_signature_line(self, node) -> str:
        """Return text up to and including colon/opening brace."""
        text = self.node_text(node)
        for delimiter in (":\n", "{\n", ":\r\n", "{\r\n"):
            idx = text.find(delimiter)
            if idx >= 0:
                return text[: idx + 1]
        first_line = text.split("\n")[0]
        return first_line

    def _node_name(self, node) -> str | None:
        """Extract declared name from class/function node."""
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

    def _decorated_inner(self, node):
        """Return inner class/function from decorated definition."""
        lang_cfg = self._ctx.lang_cfg
        for child in node.named_children:
            if child.type in (
                *lang_cfg.function_scope_types,
                *lang_cfg.class_scope_types,
            ):
                return child
        return None

    def _dfs(self, node, lines: list[str], depth: int) -> None:
        indent = "    " * depth
        ntype = node.type
        lang_cfg = self._ctx.lang_cfg

        interesting = (
            "module",
            *lang_cfg.import_types,
            *lang_cfg.function_scope_types,
            *lang_cfg.class_scope_types,
            *lang_cfg.decorator_scope_types,
        )

        if node.id in self._seen:
            return

        if ntype not in interesting:
            skel_cfg = lang_cfg.skeleton
            if depth == 0 and ntype in skel_cfg.top_level_expr_types:
                if self._symbol is None:
                    text = self.node_text(node).strip()
                    if text and (
                        text.startswith(('"""', "'''", '"', "'")) or "=" in text
                    ):
                        lines.append(text)
            for child in node.children:
                self._dfs(child, lines, depth)
            return

        if ntype in lang_cfg.import_types:
            if self._include_imports and self._symbol is None:
                lines.append(indent + self.node_text(node).strip())
            return

        if ntype in lang_cfg.decorator_scope_types:
            inner = self._decorated_inner(node)
            if inner is not None and not self._matches_symbol(inner, depth):
                self._seen.add(node.id)
                return
            for child in node.named_children:
                if child.type == "decorator":
                    lines.append(indent + self.node_text(child).strip())
                    self._seen.add(child.id)
                    continue
                if child.type in (
                    *lang_cfg.function_scope_types,
                    *lang_cfg.class_scope_types,
                ):
                    self._dfs(child, lines, depth)
                    break
            self._seen.add(node.id)
            return

        if ntype in lang_cfg.function_scope_types:
            if not self._matches_symbol(node, depth):
                self._seen.add(node.id)
                return
            lines.append(indent + self._get_signature_line(node))
            if docstr := self._get_docstring(node):
                lines.append(indent + "    " + docstr)
            lines.append(indent + "    " + ELLIPSIS)
            self._seen.add(node.id)
            return

        if ntype in lang_cfg.class_scope_types:
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
