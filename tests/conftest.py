"""Shared fixtures for the CodeRay test suite."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from coderay.core.config import (
    Config,
    EmbedderConfig,
    IndexConfig,
    _reset_config_for_testing,
)
from coderay.core.models import Chunk
from coderay.embedding.base import Embedder, EmbedTask


class MockEmbedder(Embedder):
    """Deterministic embedder returning fixed-dimension vectors for testing."""

    DIMS = 4

    @property
    def dimensions(self) -> int:
        return self.DIMS

    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask = EmbedTask.DOCUMENT,
    ) -> list[list[float]]:
        return [[float(i + 1)] * self.DIMS for i, _ in enumerate(texts)]


MOCK_CONFIG: Config = Config(
    embedder=EmbedderConfig(dimensions=MockEmbedder.DIMS),
)

SAMPLE_PYTHON = """\
import os

class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

def helper():
    g = Greeter()
    return g.greet("world")
"""

TREE_SITTER_PLAYGROUND_PATH = Path(__file__).parent / "tree_sitter_playground.py"

EXPECTED_TREE_SITTER_PLAYGROUND_SKELETON = '''"""Tree-sitter playground module for end-to-end parsing tests.

This file is intentionally eclectic: it includes a variety of Python constructs
that exercise chunking, skeleton extraction, and graph building.
"""
from __future__ import annotations
import asyncio
import dataclasses
import logging
import math as m
from collections import defaultdict as dd
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, Generic, TypeVar
logger = logging.getLogger(__name__)
T = TypeVar("T")
MY_CONST = 42
ANOTHER_CONST = "value"
def top_level_helper(x: int, y: int) -> int:
    """Return the sum of two integers."""
    ...
async def async_helper(name: str) -> str:
    """Return a greeting from an async context."""
    ...
class BaseService:
    """Base service with a simple interface."""
    def __init__(self, root: Path) -> None:
        """Initialize the base service with a root path."""
        ...
    def get_root(self) -> Path:
        """Return the root path."""
        ...
    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process a payload and return a modified copy."""
        ...
class FileService(BaseService):
    """Concrete service that works with files."""
    def read_text(self, relative: str) -> str:
        """Read and return a file as text."""
        ...
    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Override process to add file-specific metadata."""
        ...
@dataclasses.dataclass
class User:
    """Simple user model for testing."""
    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the user."""
        ...
class Repository(Generic[T]):
    """In-memory repository with basic operations."""
    def __init__(self) -> None:
        """Initialize an empty repository."""
        ...
    def add(self, key: int, item: T) -> None:
        """Add an item under the given key."""
        ...
    def get(self, key: int) -> T | None:
        """Return the item for the key, if present."""
        ...
    def all_items(self) -> list[T]:
        """Return all items in insertion order."""
        ...
def decorator(fn: Callable[..., T]) -> Callable[..., T]:
    """Example decorator that logs and forwards calls."""
    ...
def tracing(fn: Callable[..., T]) -> Callable[..., T]:
    """Second decorator to exercise stacked decorated_definition nodes."""
    ...
@decorator
def decorated_function(a: int, b: int) -> int:
    """Decorated function used to test decorated_definition nodes."""
    ...
@decorator
class DecoratedClass:
    """Decorated class used to test class-related nodes."""
    def method(self) -> str:
        """Return a fixed string."""
        ...
@decorator
@tracing
def stacked_decorated_function(radius: float) -> float:
    """Function with stacked decorators and math usage."""
    ...
def chained_calls_example(repo: Repository[User], user_id: int) -> str | None:
    """Example with chained attribute lookups and calls."""
    ...
def complex_expression_example(x: int) -> list[int]:
    """Return a list built via a comprehension."""
    ...
def local_imports_example(numbers: list[int]) -> dict[str, int]:
    """Use local imports to exercise import detection inside function bodies."""
    ...
root = Path(".")
service = FileService(root)
payload = {"value": 1}
processed = service.process(payload)'''


@pytest.fixture
def expected_tree_sitter_playground_skeleton() -> str:
    """Return the expected skeleton for tree_sitter_playground.py."""
    return EXPECTED_TREE_SITTER_PLAYGROUND_SKELETON


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    return MockEmbedder()


@pytest.fixture
def mock_config() -> Config:
    return MOCK_CONFIG


@pytest.fixture
def app_config(tmp_path: Path) -> Config:
    """Set global config for the test (index=tmp_path/.index, dimensions=4)."""
    idx = tmp_path / ".index"
    idx.mkdir()
    cfg = Config(
        index=IndexConfig(path=str(idx)),
        embedder=EmbedderConfig(dimensions=MockEmbedder.DIMS),
    )
    _reset_config_for_testing(cfg)
    yield cfg
    _reset_config_for_testing(None)


@pytest.fixture
def default_config() -> Config:
    """Reset global config to default (for tests that use get_config() default)."""
    cfg = Config()
    _reset_config_for_testing(cfg)
    yield cfg
    _reset_config_for_testing(None)


@pytest.fixture
def tmp_index_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".index"
    d.mkdir()
    return d


@pytest.fixture
def sample_python_code() -> str:
    return SAMPLE_PYTHON


@pytest.fixture
def tree_sitter_playground_source() -> tuple[str, str]:
    """Return (path, source) for the Tree-sitter playground module."""
    source = TREE_SITTER_PLAYGROUND_PATH.read_text(encoding="utf-8")
    return (str(TREE_SITTER_PLAYGROUND_PATH), source)


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            path="src/a.py",
            start_line=1,
            end_line=5,
            symbol="foo",
            content="def foo():\n    pass",
        ),
        Chunk(
            path="src/b.py",
            start_line=1,
            end_line=3,
            symbol="bar",
            content="def bar():\n    pass",
        ),
    ]


@pytest.fixture
def fake_git_repo(tmp_path: Path) -> Path | None:
    """Create a minimal git repo. Returns None (skips) if git init fails (sandbox)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        subprocess.run(
            ["git", "init"],
            cwd=repo,
            capture_output=True,
            check=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git init not available in this environment")
        return None

    py_file = repo / "hello.py"
    py_file.write_text("def hello():\n    return 'hi'\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    return repo
