from __future__ import annotations

import logging
from pathlib import Path

from coderay.chunking.registry import get_language_for_file
from coderay.parsing.base import BaseTreeSitterParser, ParserContext

logger = logging.getLogger(__name__)


class SkeletonTreeSitterParser(BaseTreeSitterParser):
    """Tree-sitter based skeleton extractor for source files."""

    def collect_lines(self) -> list[str]:
        """Return the skeleton of the file as a list of lines."""
        tree = self.get_tree()
        lines: list[str] = []
        _visit_skeleton(tree.root_node, self._source_bytes, lines, depth=0)
        return lines


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


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode(
        "utf-8", errors="replace"
    )


def _get_docstring(node, source_bytes: bytes) -> str | None:
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
                    return _node_text(sub, source_bytes)
        break
    return None


def _get_signature_line(node, source_bytes: bytes) -> str:
    """Get everything up to and including the colon/opening brace."""
    text = _node_text(node, source_bytes)
    for delimiter in (":\n", "{\n", ":\r\n", "{\r\n"):
        idx = text.find(delimiter)
        if idx >= 0:
            return text[: idx + 1]
    first_line = text.split("\n")[0]
    return first_line


def _visit_skeleton(
    node,
    source_bytes: bytes,
    lines: list[str],
    depth: int,
) -> None:
    indent = "    " * depth
    ntype = node.type

    if ntype in ("import_statement", "import_from_statement", "import_declaration"):
        lines.append(indent + _node_text(node, source_bytes).strip())
        return

    if ntype in (
        "function_definition",
        "function_declaration",
        "method_declaration",
        "method_definition",
    ):
        sig = _get_signature_line(node, source_bytes).strip()
        lines.append(indent + sig)
        docstring = _get_docstring(node, source_bytes)
        if docstring:
            lines.append(indent + "    " + docstring)
        lines.append(indent + "    ...")
        lines.append("")
        return

    if ntype in (
        "class_definition",
        "class_declaration",
        "interface_declaration",
        "type_alias_declaration",
        "type_declaration",
    ):
        sig = _get_signature_line(node, source_bytes).strip()
        lines.append(indent + sig)
        docstring = _get_docstring(node, source_bytes)
        if docstring:
            lines.append(indent + "    " + docstring)
        for child in node.children:
            if child.type in ("block", "class_body", "statement_block"):
                for member in child.children:
                    _visit_skeleton(member, source_bytes, lines, depth + 1)
        lines.append("")
        return

    if ntype in ("expression_statement",) and depth == 0:
        text = _node_text(node, source_bytes).strip()
        if text.startswith(('"""', "'''", '"', "'")):
            lines.append(indent + text)
        elif "=" in text:
            lines.append(indent + text)
        return

    if ntype in ("export_statement", "lexical_declaration") and depth == 0:
        text = _node_text(node, source_bytes)
        first_line = text.split("\n")[0].strip()
        lines.append(indent + first_line)
        return

    for child in node.children:
        _visit_skeleton(child, source_bytes, lines, depth)
