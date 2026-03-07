"""Tests for file skeleton extraction."""

from coderay.skeleton.extractor import extract_skeleton

SAMPLE_PYTHON = '''
import os
from pathlib import Path

MY_CONST = 42

class UserService:
    """Manages user operations."""

    def create_user(self, name: str, email: str) -> None:
        """Create a new user."""
        db.insert(name, email)
        logger.info("User created")

    def delete_user(self, user_id: int) -> bool:
        """Delete a user by ID."""
        return db.delete(user_id)


def helper_function(x: int) -> int:
    """A helper."""
    return x + 1
'''


class TestExtractSkeleton:
    def test_extracts_imports(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "import os" in skeleton
        assert "from pathlib import Path" in skeleton

    def test_extracts_class_signature(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "class UserService:" in skeleton

    def test_extracts_method_signatures(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "def create_user" in skeleton
        assert "def delete_user" in skeleton

    def test_extracts_function_signature(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "def helper_function" in skeleton

    def test_bodies_replaced_with_ellipsis(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "..." in skeleton
        assert "db.insert" not in skeleton
        assert "logger.info" not in skeleton

    def test_docstrings_preserved(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "Manages user operations" in skeleton

    def test_top_level_assignment(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "MY_CONST = 42" in skeleton

    def test_unsupported_extension_returns_content(self):
        content = "some random content"
        result = extract_skeleton("test.xyz", content)
        assert result == content

    def test_empty_content(self):
        result = extract_skeleton("test.py", "")
        assert isinstance(result, str)

    def test_explicit_language_param(self):
        skeleton = extract_skeleton("noext", SAMPLE_PYTHON, language="python")
        assert "def helper_function" in skeleton
