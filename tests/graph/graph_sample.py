"""Comprehensive sample module for graph extraction tests.

Covers all implemented graph features and known gaps.  Each section is
labelled so tests can reference it by name.
"""

from __future__ import annotations

# --- Imports: bare, from, aliased, multiple, relative, excluded -------
import math as m
import os
import sys
from abc import ABC, abstractmethod
from collections import defaultdict as dd
from pathlib import Path
from typing import Any, Optional

# --- Top-level definitions --------------------------------------------


PLATFORM = sys.platform
CWD = os.getcwd()


class Animal:
    """Base class with methods."""

    def speak(self) -> str:
        return "..."

    def move(self) -> str:
        return self._walk()

    def _walk(self) -> str:
        return "walking"


class Dog(Animal):
    """Inherits from a local class."""

    def speak(self) -> str:
        return self.bark()

    def bark(self) -> str:
        return "woof"


class GuideDog(Dog, ABC):
    """Multiple inheritance: local class + imported class."""

    @abstractmethod
    def guide(self) -> str: ...


class HttpClient:
    """Standalone class used for composition tests."""

    def get(self, url: str) -> Optional[str]:
        return f"GET {url}"

    def post(self, url: str, data: Any) -> str:
        return f"POST {url}"


class Service:
    """Demonstrates composition and self-method calls."""

    def __init__(self, root: Path) -> None:
        self.client = HttpClient()
        self._root = root

    def fetch(self, endpoint: str) -> str:
        return self.client.get(endpoint)

    def bootstrap(self) -> None:
        self._setup_logging()
        self._connect()

    def _setup_logging(self) -> None:
        pass

    def _connect(self) -> None:
        pass


# --- Decorated definitions --------------------------------------------


def my_decorator(fn):
    """Simple decorator."""

    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@my_decorator
def decorated_func(x: int) -> int:
    return x * 2


@my_decorator
class DecoratedClass:
    def method(self) -> str:
        return "ok"


# --- Aliases and assignments ------------------------------------------

path_func = Path
my_dd = dd
client_class = HttpClient


def use_aliases() -> None:
    """Call through aliases."""
    p = path_func(".")
    d = my_dd(int)
    c = client_class()


# --- Instance tracking ------------------------------------------------


def instance_tracking_example() -> None:
    """Local instance creation and method calls."""
    client = HttpClient()
    client.get("/api")
    client.post("/api", {"key": "value"})


# --- Module-level instantiation and method calls ----------------------

service = Service(Path("."))
result = service.fetch("/health")


# --- Chained attribute access -----------------------------------------


def chained_access_example() -> None:
    """Deep attribute chains that require type inference."""
    service = Service(Path("."))
    service.client.get("/deep")


# --- Lambda and comprehension scopes ---------------------------------


def lambda_and_comprehension_example(items: list[int]) -> list:
    """Calls inside lambdas and comprehensions."""
    transformed = list(map(lambda x: abs(x), items))
    filtered = [str(x) for x in items if isinstance(x, int)]
    return transformed + filtered


def math_usage_example(radius: float) -> float:
    """Uses the aliased math import."""
    return m.pi * radius**2


# --- Static / classmethod calls at module level -----------------------


class Config:
    """Class with a static-like factory method."""

    @staticmethod
    def from_env() -> Config:
        return Config()

    def value(self) -> str:
        return "default"


config = Config.from_env()


# --- Wildcard import (currently unsupported) --------------------------
# from os.path import *  # noqa: F403 — commented to avoid lint errors


# --- Nested classes ---------------------------------------------------


class Outer:
    class Inner:
        def inner_method(self) -> str:
            return "inner"

    def use_inner(self) -> str:
        obj = self.Inner()
        return obj.inner_method()


# --- Builtin shadowing ------------------------------------------------


def len(x):
    """Project-defined function that shadows a builtin."""
    return 0


def call_shadowed_len() -> int:
    """Should NOT be filtered — len is locally defined."""
    return len([1, 2, 3])


# --- Calls to actual builtins ----------------------------------------


def call_real_builtins() -> None:
    """These should be filtered out of the graph."""
    print("hello")
    isinstance(42, int)
    range(10)
