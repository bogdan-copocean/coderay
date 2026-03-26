"""Tests for skeleton.extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.skeleton.extractor import extract_skeleton

FIXTURES_PY = Path(__file__).parent.parent / "fixtures" / "py"

SAMPLE_PYTHON = '''
import os
from pathlib import Path
from .my_module import MyClass

MY_CONST = 42

class UserService:
    """Manages user operations."""

    def create_user(self, name: str, email: str) -> None:
        """Create a new user."""
        db.insert(name, email)
        logger.info("User created")

        def my_closure(text: str) -> None:
            """Print received value to stdout."""
            print(text)

    def delete_user(self, user_id: int) -> bool:
        """Delete a user by ID."""
        return db.delete(user_id)


def helper_function(x: int) -> int:
    """A helper."""
    return x + 1
'''


class TestExtractSkeleton:
    def test_playground_skeleton(self, expected_tree_sitter_playground_skeleton):
        """Verify skeleton extraction for the eclectic playground module."""
        path = FIXTURES_PY / "playground.py"
        skeleton = extract_skeleton(
            str(path), path.read_text(encoding="utf-8"), include_imports=True
        )
        assert skeleton == expected_tree_sitter_playground_skeleton

    @pytest.mark.parametrize(
        "path,content", [("test.xyz", "some random content"), ("noext", SAMPLE_PYTHON)]
    )
    def test_unsupported_extension_returns_content_unchanged(self, path, content):
        assert extract_skeleton(path, content) == content

    def test_include_imports_false_omits_imports_keeps_signatures(self):
        path = FIXTURES_PY / "playground.py"
        skeleton = extract_skeleton(
            str(path), path.read_text(encoding="utf-8"), include_imports=False
        )
        assert "from __future__ import annotations" not in skeleton
        assert "import asyncio" not in skeleton
        assert "import math as m" not in skeleton
        assert "from collections import defaultdict as dd" not in skeleton
        assert "from collections.abc import Callable" not in skeleton
        assert "from pathlib import Path" not in skeleton
        assert "from typing import Any, ClassVar, Generic, TypeVar" not in skeleton

    @pytest.mark.parametrize(
        "symbol,expected,not_expected",
        [
            (
                "UserService",
                [
                    "class UserService",
                    "def delete_user",
                    "def create_user",
                    "def my_closure",
                ],
                [],
            ),
            (
                "UserService.delete_user",
                ["class UserService", "def delete_user"],
                ["def create_user", "def my_closure"],
            ),
            (
                "UserService.create_user",
                ["class UserService", "def create_user", "def my_closure"],
                ["def delete_user"],
            ),
        ],
    )
    def test_dotted_symbol_preserves_class_docstring(
        self, symbol, expected, not_expected
    ):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON, symbol=symbol)
        for exp in expected:
            assert exp in skeleton
        for nexp in not_expected:
            assert nexp not in skeleton

    @pytest.mark.parametrize(
        "symbol",
        [
            ("DoesNotExist"),
            ("FakeClass.method"),
        ],
    )
    def test_unknown_symbol_returns_hint(self, symbol: str):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON, symbol=symbol)
        assert (
            f"# Symbol '{symbol}' not found. Available symbols: Path, UserService, helper_function, os"
            == skeleton
        )
