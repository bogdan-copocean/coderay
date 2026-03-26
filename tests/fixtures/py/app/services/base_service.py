"""Base service contracts for Python fixture app."""

from __future__ import annotations

from typing import Any, ClassVar


class BaseService:
    """Provide base payload processing."""

    service_name: ClassVar[str] = "base"

    def process_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return payload with service metadata."""
        return {**payload, "processed_by": self.service_name}
