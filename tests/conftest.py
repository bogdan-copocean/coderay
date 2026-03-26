"""Shared fixtures for CodeRay tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from coderay.core.config import Config, _reset_config_for_testing, config_for_repo
from coderay.core.models import Chunk
from coderay.embedding.base import Embedder, EmbedTask


class MockEmbedder(Embedder):
    """Deterministic embedder for tests."""

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
def mock_config(tmp_path: Path) -> Config:
    return config_for_repo(
        tmp_path,
        {
            "embedder": {
                "fastembed": {"dimensions": MockEmbedder.DIMS},
                "mlx": {"dimensions": MockEmbedder.DIMS},
            }
        },
    )


@pytest.fixture
def app_config(tmp_path: Path) -> Config:
    """Set global config: index=tmp_path/.coderay, dimensions=4."""
    idx = tmp_path / ".coderay"
    idx.mkdir(exist_ok=True)
    cfg = config_for_repo(
        tmp_path,
        {
            "index": {"path": str(idx)},
            "embedder": {
                "fastembed": {"dimensions": MockEmbedder.DIMS},
                "mlx": {"dimensions": MockEmbedder.DIMS},
            },
        },
    )
    _reset_config_for_testing(cfg)
    yield cfg
    _reset_config_for_testing(None)


@pytest.fixture
def default_config(tmp_path: Path) -> Config:
    """Reset global config; pin embedder to fastembed so tests are OS-agnostic."""
    cfg = config_for_repo(tmp_path, {"embedder": {"backend": "fastembed"}})
    _reset_config_for_testing(cfg)
    yield cfg
    _reset_config_for_testing(None)


@pytest.fixture(autouse=True)
def _autouse_test_config(tmp_path: Path) -> None:
    """Provide a default in-memory config for tests."""
    from coderay.core.config import ENV_REPO_ROOT

    prev = os.environ.get(ENV_REPO_ROOT)
    os.environ[ENV_REPO_ROOT] = str(Path.cwd().resolve())
    idx = tmp_path / ".coderay"
    idx.mkdir(exist_ok=True)
    cfg = config_for_repo(
        tmp_path,
        {"index": {"path": str(idx)}, "embedder": {"backend": "fastembed"}},
    )
    _reset_config_for_testing(cfg)
    yield
    _reset_config_for_testing(None)
    if prev is None:
        os.environ.pop(ENV_REPO_ROOT, None)
    else:
        os.environ[ENV_REPO_ROOT] = prev


@pytest.fixture
def tmp_index_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".coderay"
    d.mkdir(exist_ok=True)
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
    """Create a minimal git repo. Skips if git init fails."""
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
