"""Skeleton test fixtures for canonical concepts."""

# ruff: noqa: E501

EXPECTED_PY_CANONICAL_WITH_IMPORTS = """\"\"\"Canonical Python concepts for skeleton extraction tests.\"\"\"
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
    \"\"\"Return the sum of two integers.\"\"\"
    ...
async def async_helper(name: str) -> str:
    \"\"\"Return a greeting from an async context.\"\"\"
    ...
class BaseService:
    \"\"\"Base service with a simple interface.\"\"\"
    def __init__(self, root: Path) -> None:
        \"\"\"Initialize the base service with a root path.\"\"\"
        ...
    def get_root(self) -> Path:
        \"\"\"Return the root path.\"\"\"
        ...
    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        \"\"\"Process a payload and return a modified copy.\"\"\"
        ...
class FileService(BaseService):
    \"\"\"Concrete service that works with files.\"\"\"
    def read_text(self, relative: str) -> str:
        \"\"\"Read and return a file as text.\"\"\"
        ...
    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        \"\"\"Override process to add file-specific metadata.\"\"\"
        ...
@dataclasses.dataclass
class User:
    \"\"\"Simple user model for testing.\"\"\"
    def to_dict(self) -> dict[str, Any]:
        \"\"\"Return a dictionary representation of the user.\"\"\"
        ...
class Repository(Generic[T]):
    \"\"\"In-memory repository with basic operations.\"\"\"
    def __init__(self) -> None:
        \"\"\"Initialize an empty repository.\"\"\"
        ...
    def add(self, key: int, item: T) -> None:
        \"\"\"Add an item under the given key.\"\"\"
        ...
    def get(self, key: int) -> T | None:
        \"\"\"Return the item for the key, if present.\"\"\"
        ...
    def all_items(self) -> list[T]:
        \"\"\"Return all items in insertion order.\"\"\"
        ...
def decorator(fn: Callable[..., T]) -> Callable[..., T]:
    \"\"\"Example decorator that logs and forwards calls.\"\"\"
    ...
    def wrapper(*args: Any, **kwargs: Any) -> T:
        \"\"\"Log the call and forward to the wrapped function.\"\"\"
        ...
def tracing(fn: Callable[..., T]) -> Callable[..., T]:
    \"\"\"Second decorator to exercise stacked decorated_definition nodes.\"\"\"
    ...
    def inner(*args: Any, **kwargs: Any) -> T:
        ...
@decorator
def decorated_function(a: int, b: int) -> int:
    \"\"\"Decorated function used to test decorated_definition nodes.\"\"\"
    ...
@decorator
class DecoratedClass:
    \"\"\"Decorated class used to test class-related nodes.\"\"\"
    def method(self) -> str:
        \"\"\"Return a fixed string.\"\"\"
        ...
@decorator
@tracing
def stacked_decorated_function(radius: float) -> float:
    \"\"\"Function with stacked decorators and math usage.\"\"\"
    ...
def chained_calls_example(repo: Repository[User], user_id: int) -> str | None:
    \"\"\"Example with chained attribute lookups and calls.\"\"\"
    ...
def complex_expression_example(x: int) -> list[int]:
    \"\"\"Return a list built via a comprehension.\"\"\"
    ...
def local_imports_example(numbers: list[int]) -> dict[str, int]:
    \"\"\"Use local imports to exercise import detection inside function bodies.\"\"\"
    ...
    import json
    from itertools import chain as ch
root = Path(".")
service = FileService(root)
payload = {"value": 1}
processed = service.process(payload)"""

EXPECTED_PY_CANONICAL_WITHOUT_IMPORTS = """\"\"\"Canonical Python concepts for skeleton extraction tests.\"\"\"
logger = logging.getLogger(__name__)
T = TypeVar("T")
MY_CONST = 42
ANOTHER_CONST = "value"
def top_level_helper(x: int, y: int) -> int:
    \"\"\"Return the sum of two integers.\"\"\"
    ...
async def async_helper(name: str) -> str:
    \"\"\"Return a greeting from an async context.\"\"\"
    ...
class BaseService:
    \"\"\"Base service with a simple interface.\"\"\"
    def __init__(self, root: Path) -> None:
        \"\"\"Initialize the base service with a root path.\"\"\"
        ...
    def get_root(self) -> Path:
        \"\"\"Return the root path.\"\"\"
        ...
    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        \"\"\"Process a payload and return a modified copy.\"\"\"
        ...
class FileService(BaseService):
    \"\"\"Concrete service that works with files.\"\"\"
    def read_text(self, relative: str) -> str:
        \"\"\"Read and return a file as text.\"\"\"
        ...
    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        \"\"\"Override process to add file-specific metadata.\"\"\"
        ...
@dataclasses.dataclass
class User:
    \"\"\"Simple user model for testing.\"\"\"
    def to_dict(self) -> dict[str, Any]:
        \"\"\"Return a dictionary representation of the user.\"\"\"
        ...
class Repository(Generic[T]):
    \"\"\"In-memory repository with basic operations.\"\"\"
    def __init__(self) -> None:
        \"\"\"Initialize an empty repository.\"\"\"
        ...
    def add(self, key: int, item: T) -> None:
        \"\"\"Add an item under the given key.\"\"\"
        ...
    def get(self, key: int) -> T | None:
        \"\"\"Return the item for the key, if present.\"\"\"
        ...
    def all_items(self) -> list[T]:
        \"\"\"Return all items in insertion order.\"\"\"
        ...
def decorator(fn: Callable[..., T]) -> Callable[..., T]:
    \"\"\"Example decorator that logs and forwards calls.\"\"\"
    ...
    def wrapper(*args: Any, **kwargs: Any) -> T:
        \"\"\"Log the call and forward to the wrapped function.\"\"\"
        ...
def tracing(fn: Callable[..., T]) -> Callable[..., T]:
    \"\"\"Second decorator to exercise stacked decorated_definition nodes.\"\"\"
    ...
    def inner(*args: Any, **kwargs: Any) -> T:
        ...
@decorator
def decorated_function(a: int, b: int) -> int:
    \"\"\"Decorated function used to test decorated_definition nodes.\"\"\"
    ...
@decorator
class DecoratedClass:
    \"\"\"Decorated class used to test class-related nodes.\"\"\"
    def method(self) -> str:
        \"\"\"Return a fixed string.\"\"\"
        ...
@decorator
@tracing
def stacked_decorated_function(radius: float) -> float:
    \"\"\"Function with stacked decorators and math usage.\"\"\"
    ...
def chained_calls_example(repo: Repository[User], user_id: int) -> str | None:
    \"\"\"Example with chained attribute lookups and calls.\"\"\"
    ...
def complex_expression_example(x: int) -> list[int]:
    \"\"\"Return a list built via a comprehension.\"\"\"
    ...
def local_imports_example(numbers: list[int]) -> dict[str, int]:
    \"\"\"Use local imports to exercise import detection inside function bodies.\"\"\"
    ...
root = Path(".")
service = FileService(root)
payload = {"value": 1}
processed = service.process(payload)"""

EXPECTED_PY_CANONICAL_SYMBOL_REPOSITORY = """class Repository(Generic[T]):
    \"\"\"In-memory repository with basic operations.\"\"\"
    def __init__(self) -> None:
        \"\"\"Initialize an empty repository.\"\"\"
        ...
    def add(self, key: int, item: T) -> None:
        \"\"\"Add an item under the given key.\"\"\"
        ...
    def get(self, key: int) -> T | None:
        \"\"\"Return the item for the key, if present.\"\"\"
        ...
    def all_items(self) -> list[T]:
        \"\"\"Return all items in insertion order.\"\"\"
        ..."""

EXPECTED_PY_CANONICAL_SYMBOL_REPOSITORY_GET = """class Repository(Generic[T]):
    \"\"\"In-memory repository with basic operations.\"\"\"
    def get(self, key: int) -> T | None:
        \"\"\"Return the item for the key, if present.\"\"\"
        ..."""

EXPECTED_PY_CANONICAL_SYMBOL_LOCAL_IMPORTS = """def local_imports_example(numbers: list[int]) -> dict[str, int]:
    \"\"\"Use local imports to exercise import detection inside function bodies.\"\"\"
    ..."""


EXPECTED_PY_CANONICAL_SYMBOL_FUNCTION_WITH_CLOSURE = """def decorator(fn: Callable[..., T]) -> Callable[..., T]:
    \"\"\"Example decorator that logs and forwards calls.\"\"\"
    ...
    def wrapper(*args: Any, **kwargs: Any) -> T:
        \"\"\"Log the call and forward to the wrapped function.\"\"\"
        ..."""

EXPECTED_PY_CANONICAL_SYMBOL_WRAPPER = """def wrapper(*args: Any, **kwargs: Any) -> T:
    \"\"\"Log the call and forward to the wrapped function.\"\"\"
    ..."""


EXPECTED_UNKNOWN_SYMBOL_PREFIX = (
    """# Symbol '{symbol}' not found. Available symbols: """
)


EXPECTED_TS_CANONICAL_WITH_IMPORTS = (
    """import { UserRepository } from '../../fixtures/js_ts/app/data/userRepository';
import type { ApiResponse, UserRecord } from '../../fixtures/js_ts/app/types';
type Handler<T> = (value: T) => T;
interface ServiceContract {
class CoreService implements ServiceContract {
    constructor(private readonly repository: UserRepository) {}
        ...
    async loadProfile(userId: number): Promise<ApiResponse<UserRecord>> {
        ...
    withClosure(prefix: string): Handler<string> {
        ...
        (value: string): string => `${prefix}:${value}`
            ...
async function buildProfileLabel(userId: number): Promise<string> {
    ...
const buildService = (): CoreService => {
    return new CoreService(new UserRepository());
};
(): CoreService => {
    ...
"""
).rstrip("\n")


EXPECTED_TS_CANONICAL_WITHOUT_IMPORTS = (
    """type Handler<T> = (value: T) => T;
interface ServiceContract {
class CoreService implements ServiceContract {
    constructor(private readonly repository: UserRepository) {}
        ...
    async loadProfile(userId: number): Promise<ApiResponse<UserRecord>> {
        ...
    withClosure(prefix: string): Handler<string> {
        ...
        (value: string): string => `${prefix}:${value}`
            ...
async function buildProfileLabel(userId: number): Promise<string> {
    ...
const buildService = (): CoreService => {
    return new CoreService(new UserRepository());
};
(): CoreService => {
    ...
"""
).rstrip("\n")


EXPECTED_TS_SYMBOL_CORESERVICE = (
    """class CoreService implements ServiceContract {
    constructor(private readonly repository: UserRepository) {}
        ...
    async loadProfile(userId: number): Promise<ApiResponse<UserRecord>> {
        ...
    withClosure(prefix: string): Handler<string> {
        ...
        (value: string): string => `${prefix}:${value}`
            ...
"""
).rstrip("\n")


EXPECTED_TS_SYMBOL_CORESERVICE_WITH_CLOSURE = (
    """class CoreService implements ServiceContract {
    withClosure(prefix: string): Handler<string> {
        ...
        (value: string): string => `${prefix}:${value}`
            ...
"""
).rstrip("\n")


EXPECTED_TS_SYMBOL_BUILD_PROFILE_LABEL = (
    """async function buildProfileLabel(userId: number): Promise<string> {
    ...
"""
).rstrip("\n")


EXPECTED_TS_UNKNOWN_SYMBOL_PREFIX = (
    """# Symbol '{symbol}' not found. Available symbols: """
)


EXPECTED_TS_SYMBOL_WRAPPER = (
    """        (value: string): string => `${prefix}:${value}`
            ..."""
).rstrip("\n")
