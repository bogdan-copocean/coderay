"""Shared CST read surface for graph processors."""

from __future__ import annotations

from typing import Protocol

from tree_sitter import Tree

from coderay.parsing.base import ParserContext, TSNode


class SyntaxRead(Protocol):
    """Read-only access to parser context and CST text for processors."""

    @property
    def file_path(self) -> str: ...

    def node_text(self, node: TSNode) -> str: ...

    def identifier_from_node(
        self, node: TSNode, parent: TSNode | None = None
    ) -> str: ...

    def get_tree(self) -> Tree: ...

    @property
    def _ctx(self) -> ParserContext: ...
