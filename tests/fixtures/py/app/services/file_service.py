"""Concrete service extending base behavior."""

from __future__ import annotations

from typing import Any, ClassVar

from .base_service import BaseService


class FileService(BaseService):
    """Override processing for file metadata."""

    service_name: ClassVar[str] = "file"

    def process_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return payload with file service metadata."""
        base = super().process_payload(payload)
        base["kind"] = "file"
        return base
