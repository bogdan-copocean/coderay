"""Single-entry contract for CST traversal handlers."""

from __future__ import annotations

from typing import Protocol

from coderay.parsing.base import TSNode


class NodeProcessor(Protocol):
    """Handle one classified node; return a scope name to push, or None."""

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        """Process node, update session facts, return new scope name or None."""
