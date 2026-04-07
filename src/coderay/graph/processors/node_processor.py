"""Single-entry contract for CST traversal handlers."""

from __future__ import annotations

from typing import Protocol

from coderay.parsing.base import TSNode


class NodeProcessor(Protocol):
    """Handle one classified CST node.

    Returns a scope name if the handler registered a new scope (used when
    Handler.pushes_scope=True), otherwise None.
    """

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None: ...
