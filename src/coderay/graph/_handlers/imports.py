"""Import handling: IMPORTS edges and FileContext registration."""

from __future__ import annotations

from typing import Any

from coderay.graph._handlers.lang.registry import get_import_handler

TSNode = Any


class ImportHandlerMixin:
    """Handle imports: delegates to language-specific handler."""

    def _handle_import(
        self, node: TSNode, *, scope_stack: list[str] | None = None
    ) -> None:
        """Create IMPORTS edges and register names in FileContext."""
        # Resolved at runtime from the language name — no factory stored in config.
        handler = get_import_handler(self._ctx.lang_cfg.name)
        handler.handle(node, self, scope_stack=scope_stack or [])
