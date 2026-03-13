"""Shared fixtures for the CodeRay test suite."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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


MOCK_CONFIG: dict = {
    "embedder": {
        "provider": "local",
        "model": "all-MiniLM-L6-v2",
        "dimensions": MockEmbedder.DIMS,
    },
}

SAMPLE_PYTHON = """\
import os

class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

def helper():
    g = Greeter()
    return g.greet("world")
"""


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    return MockEmbedder()


@pytest.fixture
def mock_config() -> dict:
    return MOCK_CONFIG.copy()


@pytest.fixture
def tmp_index_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".index"
    d.mkdir()
    return d


@pytest.fixture
def sample_python_code() -> str:
    return SAMPLE_PYTHON


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
