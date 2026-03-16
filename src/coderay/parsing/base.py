from __future__ import annotations

"""Shared Tree-sitter parsing utilities and base classes.

This module centralizes common Tree-sitter integration so that features like
chunking, skeleton extraction, and graph building can all rely on the same
parsing primitives.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tree_sitter import Parser, Tree


@dataclass
class ParserContext:
    """Hold shared parsing state for a single file and language.

    Attributes:
        file_path: Logical path of the file being parsed.
        content: Source code contents.
        lang_cfg: Language configuration used to create the parser.
    """

    file_path: str
    content: str
    lang_cfg: Any


def parse_file(path: str | Path, content: str) -> ParserContext | None:
    """Resolve a file's language and build a parser context.

    Args:
        path: File path (used to determine the language via extension).
        content: Source code contents.

    Returns:
        A ``ParserContext`` ready for use with any ``BaseTreeSitterParser``
        subclass, or ``None`` if the file's language is not supported.
    """
    from coderay.parsing.languages import get_language_for_file

    path_str = str(path) if isinstance(path, Path) else path
    lang_cfg = get_language_for_file(path_str)
    if lang_cfg is None:
        return None
    return ParserContext(file_path=path_str, content=content, lang_cfg=lang_cfg)


class BaseTreeSitterParser:
    """Base class for Tree-sitter based analyzers.

    Subclasses should implement feature-specific logic (e.g., chunking,
    skeleton extraction, graph building) by overriding the hook methods and
    using the traversal helpers provided here.
    """

    def __init__(self, context: ParserContext) -> None:
        """Initialize the parser with file and language context."""
        self._ctx = context
        self._source_bytes: bytes = context.content.encode("utf-8")
        self._tree: Tree | None = None
        self._parser: Parser | None = None

    def get_tree(self) -> Tree:
        """Parse the source and return the syntax tree, caching the result.

        Raises:
            Exception: Propagates any errors from Tree-sitter parser creation
                or parsing. Callers that want feature-specific failure
                behavior should wrap this method.
        """
        if self._tree is not None:
            return self._tree
        if self._parser is None:
            self._parser = self._make_parser()
        self._tree = self._parser.parse(self._source_bytes)
        return self._tree

    def _make_parser(self) -> Parser:
        """Create and return a Tree-sitter parser for the current language.

        Subclasses can override this when they need custom parser behavior,
        but most callers should rely on the language configuration instead.
        """
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
        """Return the logical path of the file being parsed."""
        return self._ctx.file_path

    def node_text(self, node) -> str:
        """Decode the raw source text spanned by a syntax tree node."""
        return self._source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )

    def identifier_from_node(self, node) -> str:
        """Extract an identifier name from a definition node.

        Returns:
            The identifier text, or an empty string when no name is found.
        """
        # Unwrap decorated definitions (e.g. @decorator … def func)
        if node.type == "decorated_definition":
            inner = node.child_by_field_name("definition")
            return self.identifier_from_node(inner) if inner else ""

        # Preferred: use the grammar's "name" field (explicit, no guessing)
        name_node = node.child_by_field_name("name")
        if name_node and name_node.type in (
            "identifier",
            "type_identifier",
            "field_identifier",
        ):
            return self.node_text(name_node)

        # Fallback: scan named children for an identifier-like node
        for child in node.named_children:
            if child.type in ("identifier", "type_identifier", "field_identifier"):
                return self.node_text(child)

        # Leaf node that is itself an identifier (e.g. property_identifier)
        if node.type in ("property_identifier", "field_identifier"):
            return self.node_text(node)

        return ""
