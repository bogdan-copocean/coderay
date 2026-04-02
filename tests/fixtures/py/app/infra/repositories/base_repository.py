"""Generic base repository for Python fixture app."""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Store keyed records in memory."""

    def __init__(self) -> None:
        """Initialize empty record storage."""
        self._records: dict[int, T] = {}

    def add(self, key: int, item: T) -> None:
        """Store a record by key."""
        self._records[key] = item

    def get(self, key: int) -> T | None:
        """Return a record by key."""
        return self._records.get(key)
