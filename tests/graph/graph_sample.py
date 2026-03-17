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
from typing import Any, Self

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

    def get(self, url: str) -> str | None:
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


# --- Ports and Adapters (Hexagonal Architecture) ---------------------


class StoragePort(ABC):
    """Port interface for storage operations."""

    @abstractmethod
    def save(self, data: str) -> None: ...


class FileStorageAdapter(StoragePort):
    """Adapter implementing StoragePort."""

    def save(self, data: str) -> None:
        with open("out.txt", "w") as f:
            f.write(data)


class UseCaseWithInjectedStorage:
    """Use case that receives StoragePort via constructor injection."""

    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage

    def execute(self) -> None:
        self.storage.save("data")


# --- Function parameter injection --------------------------------------


def process_with_injected_dependency(processor: DataProcessor) -> None:
    """Processor is injected as function parameter; calls processor.process()."""
    processor.process()


class DataProcessor:
    """Processor used when injected into process_with_injected_dependency."""

    def process(self) -> str:
        return "done"


# --- Factory pattern ---------------------------------------------------


def create_http_client() -> HttpClient:
    """Factory function that returns HttpClient instance."""
    return HttpClient()


def use_factory_client() -> None:
    """Uses client from factory; client.get() should resolve to HttpClient.get."""
    client = create_http_client()
    client.get("/api")


# --- Setter injection --------------------------------------------------


class ServiceWithSetterInjection:
    """Repository injected via setter instead of constructor."""

    def set_repository(self, repo: "RepositoryPort") -> None:
        self._repo = repo

    def persist(self) -> None:
        self._repo.save()


class RepositoryPort(ABC):
    @abstractmethod
    def save(self) -> None: ...


class InMemoryRepository(RepositoryPort):
    def save(self) -> None:
        pass


# --- Callable injection ------------------------------------------------


def run_with_callback(callback) -> None:
    """Callback is injected; callback() invokes the passed callable."""
    callback()


def injected_callback() -> str:
    return "result"


# --- Property-based lazy injection -------------------------------------


class ServiceWithLazyRepo:
    """Repository accessed via property (lazy injection)."""

    def __init__(self) -> None:
        self._repo: RepositoryPort | None = None

    def set_repo(self, repo: RepositoryPort) -> None:
        self._repo = repo

    @property
    def repo(self) -> RepositoryPort:
        assert self._repo is not None
        return self._repo

    def do_work(self) -> None:
        self.repo.save()


# --- Context manager (resource injection) --------------------------------


class HttpClientContext:
    """Context manager that yields an HttpClient."""

    def __enter__(self) -> HttpClient:
        return HttpClient()

    def __exit__(self, *args: object) -> None:
        pass


def use_client_context() -> None:
    """with get_client_context() as c: c.get() — context manager injection."""
    with HttpClientContext() as client:
        client.get("/api")


# --- Classmethod factory ------------------------------------------------


class ApiClient:
    """Factory via classmethod."""

    @classmethod
    def create(cls) -> ApiClient:
        return cls()

    def request(self, path: str) -> str:
        return f"GET {path}"


def use_classmethod_factory() -> None:
    """client = ApiClient.create(); client.request() — classmethod factory."""
    client = ApiClient.create()
    client.request("/v1/data")


# --- Union type parameter injection ----------------------------------------


class HandlerA:
    def process(self) -> str:
        return "A"


class HandlerB:
    def process(self) -> str:
        return "B"


def run_with_union_handler(handler: HandlerA | HandlerB) -> None:
    """Union type param: handler.process() should create edges to both."""
    handler.process()


# --- Self return type (factory) ----------------------------------------------


class Builder:
    """Factory with Self return type."""

    @classmethod
    def create(cls) -> Self:
        return cls()

    def build(self) -> str:
        return "built"


def use_self_factory() -> None:
    """b = Builder.create(); b.build() — Self resolves to Builder."""
    b = Builder.create()
    b.build()


# --- super() calls -----------------------------------------------------------


class ParentWithRun:
    def run(self) -> str:
        return "parent"


class ChildWithSuper(ParentWithRun):
    def run(self) -> str:
        return super().run() + "-child"


# --- functools.partial --------------------------------------------------------


from functools import partial


def greeter(prefix: str, name: str) -> str:
    return f"{prefix} {name}"


def use_partial() -> None:
    """hello = partial(greeter, 'Hello'); hello('World') — resolves to greeter."""
    hello = partial(greeter, "Hello")
    hello("World")


# --- __call__ protocol -------------------------------------------------------


class CallableHandler:
    def __call__(self, x: str) -> str:
        return f"handled: {x}"


def use_callable_handler() -> None:
    """h = CallableHandler(); h('test') — resolves to CallableHandler.__call__."""
    h = CallableHandler()
    h("test")


# --- Tuple unpacking from typed factory -------------------------------------


class FirstHandler:
    def run(self) -> str:
        return "first"


class SecondHandler:
    def run(self) -> str:
        return "second"


def get_handlers() -> tuple[FirstHandler, SecondHandler]:
    """Factory returning tuple; unpacked names should resolve."""
    return FirstHandler(), SecondHandler()


def use_tuple_unpacking() -> None:
    """first, second = get_handlers(); first.run() — resolves to FirstHandler.run."""
    first, second = get_handlers()
    first.run()
    second.run()
