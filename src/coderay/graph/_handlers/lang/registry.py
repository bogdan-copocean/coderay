"""Registry mapping language names to import handler instances."""

from __future__ import annotations

from typing import Any

from coderay.graph._handlers.lang.js_ts.imports import JsTsImportHandler
from coderay.graph._handlers.lang.python.imports import PythonImportHandler

TSNode = Any


class _NoOpImportHandler:
    """No-op handler for languages without import support."""

    def handle(self, node: TSNode, parser: Any, **kwargs: Any) -> None:
        """No-op; language does not have graph import support."""


_IMPORT_HANDLERS: dict[str, object] = {
    "python": PythonImportHandler(),
    "javascript": JsTsImportHandler(),
    "typescript": JsTsImportHandler(),
}


def get_import_handler(lang_name: str) -> object:
    """Return import handler for language; no-op for unsupported."""
    return _IMPORT_HANDLERS.get(lang_name, _NoOpImportHandler())
