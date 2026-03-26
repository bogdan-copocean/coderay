"""Chunking integration tests for fixture apps."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.chunking.chunker import chunk_file

FIXTURES_ROOT = Path(__file__).parents[3] / "tests" / "fixtures"

pytestmark = pytest.mark.integration


def _chunk_symbols(path: Path) -> set[str]:
    """Return chunk symbols for a file."""
    chunks = chunk_file(path, path.read_text(encoding="utf-8"))
    return {c.symbol for c in chunks}


def _chunk_contents(path: Path) -> str:
    """Return concatenated chunk contents for a file."""
    chunks = chunk_file(path, path.read_text(encoding="utf-8"))
    return "\n".join(c.content for c in chunks)


def _has_tree_sitter_js() -> bool:
    """Return whether tree-sitter-javascript is available."""
    try:
        import tree_sitter_javascript  # noqa: F401

        return True
    except ImportError:
        return False


def _has_tree_sitter_ts() -> bool:
    """Return whether tree-sitter-typescript is available."""
    try:
        import tree_sitter_typescript as tsts

        tsts.language_typescript()
        return True
    except (ImportError, AttributeError):
        return False


class TestPyAppChunking:
    def test_main_chunks_endpoint_functions(self) -> None:
        path = FIXTURES_ROOT / "py" / "app" / "main.py"
        symbols = _chunk_symbols(path)
        assert "handle_request" in symbols
        assert "handle_request_async" in symbols

    def test_user_service_chunks_core_methods(self) -> None:
        path = FIXTURES_ROOT / "py" / "app" / "services" / "user_service.py"
        symbols = _chunk_symbols(path)
        assert "UserService" in symbols
        assert "load_profile" in symbols
        assert "load_profile_async" in symbols
        assert "decorated_multiplier" in symbols


@pytest.mark.skipif(
    not (_has_tree_sitter_js() and _has_tree_sitter_ts()),
    reason="tree-sitter-javascript and tree-sitter-typescript required",
)
class TestJsTsAppChunking:
    def test_index_chunks_entrypoints(self) -> None:
        path = FIXTURES_ROOT / "js_ts" / "app" / "index.ts"
        symbols = _chunk_symbols(path)
        assert "startApp" in symbols
        assert "bootstrap" in symbols

    def test_user_service_chunks_profile_and_promises(self) -> None:
        path = FIXTURES_ROOT / "js_ts" / "app" / "services" / "userService.ts"
        symbols = _chunk_symbols(path)
        assert "loadProfile" in symbols
        assert "loadProfileAsync" in symbols
        assert "mapUsers" in symbols
        content = _chunk_contents(path)
        assert "class UserService" in content

    def test_router_chunks_expose_register_routes(self) -> None:
        path = FIXTURES_ROOT / "js_ts" / "app" / "api" / "http" / "router.js"
        content = _chunk_contents(path)
        assert "registerRoutes" in content
