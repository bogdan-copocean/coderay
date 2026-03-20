"""Tests for skeleton.extractor."""

import pytest

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
    def test_returns_original_content_for_unsupported_language(self) -> None:
        """Ensure non-supported files are passed through unchanged."""
        content = "just some text"
        result = extract_skeleton("notes.txt", content)
        assert result == content

    def test_simple_function_signature(self) -> None:
        """Extract a single Python function signature with ellipsis."""
        code = "def hello(name: str) -> str:\n    return f'hi {name}'\n"
        result = extract_skeleton("example.py", code)
        assert "def hello" in result
        assert "..." in result

    def test_extracts_imports_when_requested(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON, include_imports=True)
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

    def test_extracts_closure(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "def my_closure" in skeleton

    def test_docstrings_preserved(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "Manages user operations" in skeleton

    def test_top_level_assignment(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON)
        assert "MY_CONST = 42" in skeleton

    @pytest.mark.parametrize(
        "path,content", [("test.xyz", "some random content"), ("noext", SAMPLE_PYTHON)]
    )
    def test_unsupported_extension_returns_content_unchanged(self, path, content):
        assert extract_skeleton(path, content) == content

    def test_tree_sitter_playground_skeleton(
        self, tree_sitter_playground_source, expected_tree_sitter_playground_skeleton
    ):
        """Verify skeleton extraction for the eclectic tree_sitter_playground module."""
        path, source = tree_sitter_playground_source
        skeleton = extract_skeleton(path, source, include_imports=True)
        assert skeleton == expected_tree_sitter_playground_skeleton

    def test_include_imports_false_omits_imports_keeps_signatures(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON, include_imports=False)
        assert (
            "import os" not in skeleton and "from pathlib import Path" not in skeleton
        )
        assert "class UserService:" in skeleton and "def create_user" in skeleton
        assert "def helper_function" in skeleton and "MY_CONST = 42" in skeleton

    @pytest.mark.parametrize(
        "symbol,present,absent",
        [
            (
                "UserService",
                ["class UserService:", "def create_user", "def delete_user"],
                ["def helper_function", "MY_CONST"],
            ),
            ("helper_function", ["def helper_function"], ["class UserService"]),
            (
                "NonExistent",
                ["Symbol 'NonExistent' not found"],
                ["class UserService:", "def helper_function", "MY_CONST = 42"],
            ),
        ],
    )
    def test_symbol_filter(self, symbol, present, absent):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON, symbol=symbol)
        for s in present:
            assert s in skeleton
        for s in absent:
            assert s not in skeleton

    def test_symbol_filter_omits_imports(self):
        skeleton = extract_skeleton(
            "test.py", SAMPLE_PYTHON, include_imports=True, symbol="UserService"
        )
        assert "import os" not in skeleton
        assert "class UserService:" in skeleton

    # ------------------------------------------------------------------
    # B4: dotted Class.method symbol returns only the named method
    # ------------------------------------------------------------------

    def test_dotted_symbol_returns_single_method(self):
        """Class.method symbol scopes skeleton to that one method."""
        skeleton = extract_skeleton(
            "test.py", SAMPLE_PYTHON, symbol="UserService.create_user"
        )
        assert "class UserService:" in skeleton
        assert "def create_user" in skeleton
        assert "def delete_user" not in skeleton
        assert "def helper_function" not in skeleton

    def test_dotted_symbol_preserves_class_docstring(self):
        skeleton = extract_skeleton(
            "test.py", SAMPLE_PYTHON, symbol="UserService.delete_user"
        )
        assert "Manages user operations" in skeleton
        assert "def delete_user" in skeleton
        assert "def create_user" not in skeleton

    def test_plain_class_symbol_returns_all_methods(self):
        """Without the method part, all methods are included."""
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON, symbol="UserService")
        assert "def create_user" in skeleton
        assert "def delete_user" in skeleton

    # ------------------------------------------------------------------
    # B5: unknown symbol returns diagnostic hint
    # ------------------------------------------------------------------

    def test_unknown_symbol_returns_hint(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON, symbol="DoesNotExist")
        assert "not found" in skeleton.lower()
        assert "UserService" in skeleton
        assert "helper_function" in skeleton

    def test_unknown_dotted_symbol_returns_hint(self):
        skeleton = extract_skeleton("test.py", SAMPLE_PYTHON, symbol="FakeClass.method")
        assert "not found" in skeleton.lower()

    def test_javascript_skeleton(self):
        """Extract JS class and function signatures with ellipsis."""
        code = """
import { fetch } from './api';

const MY_CONST = 42;

class UserService {
    "Manages user operations."

    createUser(name, email) {
        return db.insert(name, email);
    }
}

function helperFunction(x) {
    "A helper."
    return x + 1;
}
"""
        try:
            import tree_sitter_javascript  # noqa: F401
        except ImportError:
            pytest.skip("tree-sitter-javascript not installed")

        skeleton = extract_skeleton("test.js", code)
        assert "class UserService" in skeleton
        assert "createUser" in skeleton
        assert "function helperFunction" in skeleton
        assert "..." in skeleton
        assert "db.insert" not in skeleton
        assert "MY_CONST" in skeleton

    def test_javascript_skeleton_with_imports(self):
        """JS imports included when requested."""
        code = "import { foo } from './bar';\nfunction baz() {}\n"
        try:
            import tree_sitter_javascript  # noqa: F401
        except ImportError:
            pytest.skip("tree-sitter-javascript not installed")

        skeleton = extract_skeleton("test.js", code, include_imports=True)
        assert "import { foo }" in skeleton
        assert "function baz" in skeleton
