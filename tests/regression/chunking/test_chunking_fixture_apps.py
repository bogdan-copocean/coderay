from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from coderay.chunking.chunker import chunk_file
from coderay.core.models import Chunk
from tests.regression.chunking.expected_py_app_chunks import (
    MAIN_PY_HANDLE_REQUEST_ASYNC_CHUNK,
    MAIN_PY_HANDLE_REQUEST_CHUNK,
    MAIN_PY_MODULE_CHUNK,
    USER_SERVICE_PY_BUILD_FORMATTER_CHUNK,
    USER_SERVICE_PY_CHAIN_EMAIL_LOOKUP_CHUNK,
    USER_SERVICE_PY_DECORATED_FORMATTER_CHUNK,
    USER_SERVICE_PY_DECORATED_MULTIPLIER_CHUNK,
    USER_SERVICE_PY_FORMAT_CHUNK,
    USER_SERVICE_PY_FORMATTER_CHUNK,
    USER_SERVICE_PY_GET_FORMATTER_CHUNK,
    USER_SERVICE_PY_INIT_CHUNK,
    USER_SERVICE_PY_LOAD_PROFILE_ASYNC_CHUNK,
    USER_SERVICE_PY_LOAD_PROFILE_CHUNK,
    USER_SERVICE_PY_MODULE_CHUNK,
    USER_SERVICE_PY_USER_SERVICE_CHUNK,
)

FIXTURES_ROOT = Path(__file__).parents[3] / "tests" / "fixtures"


def _chunk_symbols(path: Path) -> set[str]:
    chunks = chunk_file(path, path.read_text(encoding="utf-8"))
    return {c.symbol for c in chunks}


def _chunk_contents(path: Path) -> str:
    chunks = chunk_file(path, path.read_text(encoding="utf-8"))
    return "\n".join(c.content for c in chunks)


def _has_tree_sitter_js() -> bool:
    try:
        import tree_sitter_javascript  # noqa: F401

        return True
    except ImportError:
        return False


def _has_tree_sitter_ts() -> bool:
    try:
        import tree_sitter_typescript as tsts

        tsts.language_typescript()
        return True
    except (ImportError, AttributeError):
        return False


class TestPyAppChunking:
    def test_main_chunks_endpoint_functions(self) -> None:
        """Assert main.py chunks endpoints and functions."""
        path = FIXTURES_ROOT / "py" / "app" / "main.py"
        chunks = chunk_file(path, path.read_text(encoding="utf-8"))
        expected_chunks = [
            Chunk(
                path=str(path),
                start_line=1,
                end_line=32,
                symbol="<module>",
                content=MAIN_PY_MODULE_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=13,
                end_line=17,
                symbol="handle_request",
                content=MAIN_PY_HANDLE_REQUEST_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=20,
                end_line=24,
                symbol="handle_request_async",
                content=MAIN_PY_HANDLE_REQUEST_ASYNC_CHUNK,
            ),
        ]
        assert len(chunks) == len(expected_chunks)
        assert Counter(chunks) == Counter(expected_chunks)

    def test_user_service_chunks_core_methods(self) -> None:
        path = FIXTURES_ROOT / "py" / "app" / "services" / "user_service.py"
        chunks = chunk_file(path, path.read_text(encoding="utf-8"))
        expected_chunks = [
            Chunk(
                path=str(path),
                start_line=1,
                end_line=97,
                symbol="<module>",
                content=USER_SERVICE_PY_MODULE_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=19,
                end_line=25,
                symbol="DecoratedFormatter",
                content=USER_SERVICE_PY_DECORATED_FORMATTER_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=23,
                end_line=25,
                symbol="format",
                content=USER_SERVICE_PY_FORMAT_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=28,
                end_line=32,
                symbol="decorated_multiplier",
                content=USER_SERVICE_PY_DECORATED_MULTIPLIER_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=35,
                end_line=38,
                symbol="chain_email_lookup",
                content=USER_SERVICE_PY_CHAIN_EMAIL_LOOKUP_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=41,
                end_line=90,
                symbol="UserService",
                content=USER_SERVICE_PY_USER_SERVICE_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=44,
                end_line=48,
                symbol="__init__",
                content=USER_SERVICE_PY_INIT_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=50,
                end_line=57,
                symbol="_build_formatter",
                content=USER_SERVICE_PY_BUILD_FORMATTER_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=53,
                end_line=55,
                symbol="formatter",
                content=USER_SERVICE_PY_FORMATTER_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=59,
                end_line=83,
                symbol="load_profile",
                content=USER_SERVICE_PY_LOAD_PROFILE_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=85,
                end_line=90,
                symbol="load_profile_async",
                content=USER_SERVICE_PY_LOAD_PROFILE_ASYNC_CHUNK,
            ),
            Chunk(
                path=str(path),
                start_line=93,
                end_line=96,
                symbol="get_formatter",
                content=USER_SERVICE_PY_GET_FORMATTER_CHUNK,
            ),
        ]
        assert len(chunks) == len(expected_chunks)
        assert Counter(chunks) == Counter(expected_chunks)


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
