"""Domain models for Python fixture app."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any


@dataclass
class User:
    """Represent a user."""

    user_id: int
    name: str
    email: str

    def to_dict(self) -> dict[str, Any]:
        """Return dataclass payload as a dictionary."""
        return dataclasses.asdict(self)
