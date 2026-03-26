"""Decorator helpers for Python fixture app."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def audit(fn: Callable[..., T]) -> Callable[..., T]:
    """Wrap callable with audit metadata."""

    def wrapper(*args: Any, **kwargs: Any) -> T:
        """Forward call through audit wrapper."""
        return fn(*args, **kwargs)

    return wrapper


def trace(fn: Callable[..., T]) -> Callable[..., T]:
    """Wrap callable with trace metadata."""

    def inner(*args: Any, **kwargs: Any) -> T:
        """Forward call through trace wrapper."""
        return fn(*args, **kwargs)

    return inner
