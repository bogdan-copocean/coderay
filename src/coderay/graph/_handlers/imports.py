"""Import handling: IMPORTS edges and FileContext registration."""

from __future__ import annotations

from typing import Any

TSNode = Any


class ImportHandlerMixin:
    """Handle imports: delegates to language-specific handler."""

    def _handle_import(
        self, node: TSNode, *, scope_stack: list[str] | None = None
    ) -> None:
        """Create IMPORTS edges and register names in FileContext."""
        handler = self._lc.import_handler_factory()
        handler.handle(node, self, scope_stack=scope_stack or [])
