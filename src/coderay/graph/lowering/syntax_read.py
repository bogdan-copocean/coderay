"""Read-only CST surface for graph processors."""

from __future__ import annotations

from typing import Any, Protocol

from tree_sitter import Tree

from coderay.parsing.base import TSNode


class SyntaxRead(Protocol):
    """Read-only access to the CST and language config for processors."""

    @property
    def file_path(self) -> str: ...

    @property
    def lang_cfg(self) -> Any: ...

    def node_text(self, node: TSNode) -> str: ...

    def identifier_from_node(
        self, node: TSNode, parent: TSNode | None = None
    ) -> str: ...

    def get_tree(self) -> Tree: ...
