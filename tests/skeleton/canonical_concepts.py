"""Canonical Python concepts for skeleton extraction tests."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import math as m
from collections import defaultdict as dd
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, Generic, TypeVar

from tests.fixtures.py.app.domain.models import User as FixtureUser
from tests.fixtures.py.app.services.user_service import (
    UserService as FixtureUserService,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

MY_CONST = 42
ANOTHER_CONST = "value"


def top_level_helper(x: int, y: int) -> int:
    """Return the sum of two integers."""
    return x + y


async def async_helper(name: str) -> str:
    """Return a greeting from an async context."""
    await asyncio.sleep(0)
    return f"hello {name}"


class BaseService:
    """Base service with a simple interface."""

    service_name: ClassVar[str] = "base"

    def __init__(self, root: Path) -> None:
        """Initialize the base service with a root path."""
        self._root = root

    def get_root(self) -> Path:
        """Return the root path."""
        return self._root

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process a payload and return a modified copy."""
        return {**payload, "processed_by": self.service_name}


class FileService(BaseService):
    """Concrete service that works with files."""

    service_name: ClassVar[str] = "file"

    def read_text(self, relative: str) -> str:
        """Read and return a file as text."""
        path = self._root / relative
        return path.read_text(encoding="utf-8")

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Override process to add file-specific metadata."""
        base = super().process(payload)
        base["kind"] = "file"
        return base


@dataclasses.dataclass
class User:
    """Simple user model for testing."""

    id: int
    name: str
    email: str

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the user."""
        return dataclasses.asdict(self)


class Repository(Generic[T]):
    """In-memory repository with basic operations."""

    def __init__(self) -> None:
        """Initialize an empty repository."""
        self._items: dict[int, T] = {}

    def add(self, key: int, item: T) -> None:
        """Add an item under the given key."""
        self._items[key] = item

    def get(self, key: int) -> T | None:
        """Return the item for the key, if present."""
        return self._items.get(key)

    def all_items(self) -> list[T]:
        """Return all items in insertion order."""
        return list(self._items.values())


def decorator(fn: Callable[..., T]) -> Callable[..., T]:
    """Example decorator that logs and forwards calls."""

    def wrapper(*args: Any, **kwargs: Any) -> T:
        """Log the call and forward to the wrapped function."""
        logger.info("Calling %s with %r %r", fn.__name__, args, kwargs)
        return fn(*args, **kwargs)

    return wrapper


def tracing(fn: Callable[..., T]) -> Callable[..., T]:
    """Second decorator to exercise stacked decorated_definition nodes."""

    def inner(*args: Any, **kwargs: Any) -> T:
        logger.debug("Tracing %s", fn.__name__)
        return fn(*args, **kwargs)

    return inner


@decorator
def decorated_function(a: int, b: int) -> int:
    """Decorated function used to test decorated_definition nodes."""
    return a * b


@decorator
class DecoratedClass:
    """Decorated class used to test class-related nodes."""

    def method(self) -> str:
        """Return a fixed string."""
        return "ok"


@decorator
@tracing
def stacked_decorated_function(radius: float) -> float:
    """Function with stacked decorators and math usage."""
    area = m.pi * radius**2
    return round(area, 2)


def chained_calls_example(repo: Repository[User], user_id: int) -> str | None:
    """Example with chained attribute lookups and calls."""
    user = repo.get(user_id)
    return user.to_dict().get("email") if user else None


def complex_expression_example(x: int) -> list[int]:
    """Return a list built via a comprehension."""
    return [y * 2 for y in range(x)]


def local_imports_example(numbers: list[int]) -> dict[str, int]:
    """Use local imports to exercise import detection inside function bodies."""
    import json
    from itertools import chain as ch

    doubled = [n * 2 for n in numbers]
    grouped: dict[str, int] = dd(int)
    for val in ch(numbers, doubled):
        grouped["total"] += val
    logger.info("local_imports_example: %s", json.dumps(grouped, sort_keys=True))
    return grouped


if __name__ == "__main__":
    root = Path(".")
    service = FileService(root)
    payload = {"value": 1}
    processed = service.process(payload)
    logger.info("Processed payload: %r", processed)
