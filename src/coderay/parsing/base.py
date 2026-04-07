"""Shared Tree-sitter parsing utilities and base classes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tree_sitter import Parser, Tree

TSNode = Any


@dataclass
class ParseResult:
    """File parse outcome: language id, path, syntax tree, source bytes."""

    language_id: str
    file_path: str
    tree: Tree
    source_bytes: bytes


@dataclass
class ParserContext:
    """Hold parsing state for a file and language."""

    file_path: str
    content: str
    lang_cfg: Any


def get_parse_context(path: str | Path, content: str) -> ParserContext | None:
    """Resolve language by path and build parser context; None if unsupported."""
    from coderay.parsing.languages import get_language_for_file

    path_str = str(path) if isinstance(path, Path) else path
    lang_cfg = get_language_for_file(path_str)
    if lang_cfg is None:
        return None
    return ParserContext(file_path=path_str, content=content, lang_cfg=lang_cfg)


class BaseTreeSitterParser:
    """Base for Tree-sitter analyzers (chunking, skeleton, graph)."""

    def __init__(self, context: ParserContext) -> None:
        """Initialize parser with file and language context."""
        self._ctx = context
        self._source_bytes: bytes = context.content.encode("utf-8")
        self._tree: Tree | None = None
        self._parser: Parser | None = None

    def get_tree(self) -> Tree:
        """Parse source and return syntax tree (cached)."""
        if self._tree is not None:
            return self._tree
        if self._parser is None:
            self._parser = self._make_parser()
        self._tree = self._parser.parse(self._source_bytes)
        return self._tree

    def _make_parser(self) -> Parser:
        """Create Tree-sitter parser for current language."""
        from tree_sitter import Language  # local import to avoid cycles

        lang_handle = self._ctx.lang_cfg.language_fn()
        lang = Language(lang_handle)
        parser = Parser(lang)
        return parser

    # ------------------------------------------------------------------
    # Basic helpers
    # ------------------------------------------------------------------

    @property
    def file_path(self) -> str:
        return self._ctx.file_path

    @property
    def lang_cfg(self):
        return self._ctx.lang_cfg

    def node_text(self, node) -> str:
        """Return source text for node."""
        return self._source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )

    def identifier_from_node(self, node, parent=None) -> str:
        """Extract identifier from definition node; empty if none."""
        # Unwrap decorated definitions (e.g. @decorator … def func)
        if node.type == "decorated_definition":
            inner = node.child_by_field_name("definition")
            return self.identifier_from_node(inner) if inner else ""

        # Arrow function: const foo = () => {} — name from variable_declarator
        p = parent if parent is not None else getattr(node, "parent", None)
        if node.type == "arrow_function" and p and p.type == "variable_declarator":
            name_node = p.child_by_field_name("name")
            if name_node and name_node.type == "identifier":
                return self.node_text(name_node)

        # Preferred: use the grammar's "name" field (explicit, no guessing)
        name_node = node.child_by_field_name("name")
        id_types = (
            "identifier",
            "type_identifier",
            "field_identifier",
            "property_identifier",
        )
        if name_node and name_node.type in id_types:
            return self.node_text(name_node)

        # Fallback: scan named children for an identifier-like node
        for child in node.named_children:
            if child.type in id_types:
                return self.node_text(child)

        # Leaf node that is itself an identifier (e.g. property_identifier)
        if node.type in ("property_identifier", "field_identifier"):
            return self.node_text(node)

        return ""
