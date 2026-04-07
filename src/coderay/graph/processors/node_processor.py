"""Single-entry contract for CST traversal handlers."""

from __future__ import annotations

from typing import Protocol

from coderay.parsing.base import TSNode


class NodeProcessor(Protocol):
    """Handle one classified node; scope_stack is the enclosing qualified path."""

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Process node and update session facts / file context."""


# ImportProcessor (``processors/imports.py``) is the same surface: only ``handle``.
