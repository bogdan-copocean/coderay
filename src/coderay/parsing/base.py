from __future__ import annotations

"""Shared Tree-sitter parsing utilities and base classes.

This module centralizes common Tree-sitter integration so that features like
chunking, skeleton extraction, and graph building can all rely on the same
parsing primitives.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from tree_sitter import Parser, Tree


class HasTreeSitterLanguage(Protocol):
    """Protocol for objects that can provide a Tree-sitter Language handle."""

    def language_fn(self) -> Any:  # pragma: no cover - structural typing only
        ...


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

        This is a shared implementation used by multiple analyzers. It prefers
        identifier-like child nodes and falls back to an empty string when no
        suitable name is found.
        """
        for child in getattr(node, "children", []):
            if child.type in ("identifier", "type_identifier", "field_identifier"):
                return self.node_text(child)
        return ""

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def walk(
        self,
        node,
        *,
        pre_visit: Callable[[Any], None] | None = None,
        post_visit: Callable[[Any], None] | None = None,
    ) -> None:
        """Depth-first walk of the syntax tree.

        Args:
            node: Current Tree-sitter node.
            pre_visit: Optional callback executed before visiting children.
            post_visit: Optional callback executed after visiting children.
        """
        if pre_visit is not None:
            pre_visit(node)
        for child in getattr(node, "children", []):
            self.walk(child, pre_visit=pre_visit, post_visit=post_visit)
        if post_visit is not None:
            post_visit(node)
