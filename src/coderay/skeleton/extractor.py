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
    include_imports: bool = True,
) -> str:
    """Extract the skeleton of a source file (signatures, no bodies).

    Args:
        path: Source file path (used for language detection).
        content: Full file content.
        include_imports: When False, import statements are omitted from
            the output to reduce noise.
    """
    ctx = parse_file(path, content)
    if ctx is None:
        return content

    parser = SkeletonTreeSitterParser(ctx, include_imports=include_imports)
    try:
        lines = parser.collect_lines()
    except Exception:  # pragma: no cover - defensive fallback
        logger.exception("Skeleton extraction failed")
        return content
    return "\n".join(lines)


class SkeletonTreeSitterParser(BaseTreeSitterParser):
    """Tree-sitter based skeleton extractor for source files."""

    def __init__(self, context, *, include_imports: bool = True) -> None:
        super().__init__(context)
        self._include_imports = include_imports

    def collect_lines(self) -> list[str]:
        """Return the skeleton of a file as a list of lines."""
        tree = self.get_tree()
        lines: list[str] = []
        self._seen = set()
        self._dfs(tree.root_node, lines, depth=0)
        return lines

    def _extract_text(self, node) -> str | None:
        """Extract string text from an expression_statement, or None."""
        if node.type == "expression_statement":
            for sub in node.children:
                if sub.type == "string":
                    return self.node_text(sub).strip()
        return None

    def _get_docstring(self, node) -> str | None:
        """Extract docstring from the first child of the body block, if present."""
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
        """Get everything up to and including the colon/opening brace."""
        text = self.node_text(node)
        for delimiter in (":\n", "{\n", ":\r\n", "{\r\n"):
            idx = text.find(delimiter)
            if idx >= 0:
                return text[: idx + 1]
        first_line = text.split("\n")[0]
        return first_line

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
                text = self.node_text(node).strip()

                if text and (text.startswith(('"""', "'''", '"', "'")) or "=" in text):
                    lines.append(text)
            for child in node.children:
                self._dfs(child, lines, depth)
            return

        if ntype in lang_cfg.import_types:
            if self._include_imports:
                lines.append(indent + self.node_text(node).strip())
            return

        if ntype in lang_cfg.decorator_scope_types:
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
            lines.append(indent + self._get_signature_line(node))
            if docstr := self._get_docstring(node):
                lines.append(indent + "    " + docstr)
            lines.append(indent + "    " + ELLIPSIS)
            self._seen.add(node.id)
            return

        if ntype in lang_cfg.class_scope_types:
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
