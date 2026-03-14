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
from coderay.embedding.base import Embedder


class MockEmbedder(Embedder):
    """Deterministic embedder returning fixed-dimension vectors for testing."""

    DIMS = 4

    @property
    def dimensions(self) -> int:
        return self.DIMS

    def embed(self, texts: list[str]) -> list[list[float]]:
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
