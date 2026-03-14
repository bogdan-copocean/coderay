from __future__ import annotations

import logging
from pathlib import Path

from coderay.chunking.registry import get_language_for_file
from coderay.parsing.base import BaseTreeSitterParser, ParserContext

logger = logging.getLogger(__name__)

ELLIPSIS = "..."


def extract_skeleton(
    path: str | Path,
    content: str,
) -> str:
    """Extract the skeleton of a source file (signatures, no bodies)."""
    path_str = str(path)
    lang_cfg = get_language_for_file(path_str)
    if lang_cfg is None:
        return content

    context = ParserContext(file_path=path_str, content=content, lang_cfg=lang_cfg)
    parser = SkeletonTreeSitterParser(context)
    try:
        lines = parser.collect_lines()
    except Exception:  # pragma: no cover - defensive fallback
        return content
    return "\n".join(lines)


class SkeletonTreeSitterParser(BaseTreeSitterParser):
    """Tree-sitter based skeleton extractor for source files."""

    def collect_lines(self) -> list[str]:
        """Return the skeleton of a file as a list of lines."""
        tree = self.get_tree()
        lines: list[str] = []
        self._visit_skeleton(tree.root_node, lines, depth=0)
        return lines

    def _get_docstring(self, node) -> str | None:
        """Extract docstring from the first child of the body block, if present."""
        if not hasattr(node, "children"):
            return None
        body = None
        for child in node.children:
            if child.type in ("block", "statement_block"):
                body = child
                break
        if body is None:
            return None
        for child in body.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        return self.node_text(sub)
            break
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

    def _visit_skeleton(
        self,
        node,
        lines: list[str],
        depth: int,
    ) -> None:
        indent = "    " * depth
        ntype = node.type

        lang_cfg = self._ctx.lang_cfg.skeleton
        if ntype in lang_cfg.import_types:
            lines.append(indent + self.node_text(node).strip())
            return

        if ntype in lang_cfg.function_scope_types:
            sig = self._get_signature_line(node).strip()
            lines.append(indent + sig)
            docstring = self._get_docstring(node)
            if docstring:
                lines.append(indent + "    " + docstring)
            lines.append(indent + f"    {ELLIPSIS}")
            lines.append("")
            return

        class_like_types = tuple(lang_cfg.class_scope_types) + tuple(
            lang_cfg.extra_class_like_types
        )
        if ntype in class_like_types:
            sig = self._get_signature_line(node).strip()
            lines.append(indent + sig)
            docstring = self._get_docstring(node)
            if docstring:
                lines.append(indent + "    " + docstring)
            for child in node.children:
                if child.type in ("block", "class_body", "statement_block"):
                    for member in child.children:
                        self._visit_skeleton(member, lines, depth + 1)
            lines.append("")
            return

        if ntype in lang_cfg.top_level_expr_types and depth == 0:
            text = self.node_text(node).strip()
            if text.startswith(('"""', "'''", '"', "'")) or "=" in text:
                lines.append(indent + text)
            return

        if ntype in lang_cfg.export_like_types and depth == 0:
            text = self.node_text(node)
            first_line = text.split("\n")[0].strip()
            lines.append(indent + first_line)
            return

        for child in node.children:
            self._visit_skeleton(child, lines, depth)
