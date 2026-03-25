"""Skeleton extraction tests for JavaScript and TypeScript fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.skeleton.extractor import extract_skeleton

FIXTURES = Path(__file__).parent.parent / "fixtures" / "js_ts"


def _skeleton(filename: str, **kwargs) -> str:
    path = FIXTURES / filename
    return extract_skeleton(str(path), path.read_text(encoding="utf-8"), **kwargs)


# ---------------------------------------------------------------------------
# userService.js — class, methods, top-level function
# ---------------------------------------------------------------------------


class TestUserService:
    def test_class_and_methods_present(self) -> None:
        skeleton = _skeleton("userService.js")
        assert "class UserService" in skeleton
        assert "fetchUsers" in skeleton
        assert "createUser" in skeleton
        assert "_toDTO" in skeleton

    def test_top_level_function_present(self) -> None:
        assert "createUserService" in _skeleton("userService.js")

    def test_ellipsis_present(self) -> None:
        assert "..." in _skeleton("userService.js")

    def test_no_implementation_lines(self) -> None:
        skeleton = _skeleton("userService.js")
        assert "logger.info" not in skeleton
        assert "repository.findAll" not in skeleton

    def test_imports_included_when_requested(self) -> None:
        skeleton = _skeleton("userService.js", include_imports=True)
        assert "import" in skeleton


# ---------------------------------------------------------------------------
# apiClient.ts — generic methods, private method, top-level arrow
# ---------------------------------------------------------------------------


class TestApiClient:
    def test_class_and_methods_present(self) -> None:
        skeleton = _skeleton("apiClient.ts")
        assert "class ApiClient" in skeleton
        assert "get" in skeleton
        assert "post" in skeleton

    def test_private_method_present(self) -> None:
        assert "_parseResponse" in _skeleton("apiClient.ts")

    def test_top_level_arrow_present(self) -> None:
        assert "createApiClient" in _skeleton("apiClient.ts")

    def test_ellipsis_present(self) -> None:
        assert "..." in _skeleton("apiClient.ts")

    def test_no_implementation_lines(self) -> None:
        skeleton = _skeleton("apiClient.ts")
        assert "res.json()" not in skeleton
        assert "JSON.stringify" not in skeleton

    def test_imports_included_when_requested(self) -> None:
        assert "import" in _skeleton("apiClient.ts", include_imports=True)


# ---------------------------------------------------------------------------
# callbackService.ts — Promise and nested callback patterns
# ---------------------------------------------------------------------------


class TestCallbackService:
    def test_class_header_present(self) -> None:
        assert "class TaskRunner" in _skeleton("callbackService.ts")

    def test_all_method_signatures_present(self) -> None:
        skeleton = _skeleton("callbackService.ts")
        assert "run(" in skeleton
        assert "runAsync(" in skeleton
        assert "inspect(" in skeleton

    def test_ellipsis_present(self) -> None:
        assert "..." in _skeleton("callbackService.ts")

    def test_no_implementation_lines(self) -> None:
        skeleton = _skeleton("callbackService.ts")
        assert "lib.execute" not in skeleton
        assert "resolve(" not in skeleton

    def test_anonymous_functions_not_emitted_as_signatures(self) -> None:
        """Anonymous arrow functions used as values must not appear as signatures."""
        skeleton = _skeleton("callbackService.ts")
        assert "(resolve)" not in skeleton
        assert "(err, output)" not in skeleton

    def test_symbol_filter_scopes_to_class(self) -> None:
        skeleton = _skeleton("callbackService.ts", symbol="TaskRunner")
        assert "class TaskRunner" in skeleton
        assert "runAsync(" in skeleton
        assert "(resolve)" not in skeleton


# ---------------------------------------------------------------------------
# streamProcessor.ts — async generator with yield* delegation
# ---------------------------------------------------------------------------


class TestStreamProcessor:
    def test_class_header_present(self) -> None:
        assert "class StreamProcessor" in _skeleton("streamProcessor.ts")

    def test_all_method_signatures_present(self) -> None:
        skeleton = _skeleton("streamProcessor.ts")
        assert "process(" in skeleton
        assert "handleData(" in skeleton
        assert "handleControl(" in skeleton

    def test_ellipsis_present(self) -> None:
        assert "..." in _skeleton("streamProcessor.ts")

    def test_no_yield_star_lines(self) -> None:
        assert "yield*" not in _skeleton("streamProcessor.ts")

    def test_no_for_await_lines(self) -> None:
        assert "for await" not in _skeleton("streamProcessor.ts")

    def test_no_yield_literals(self) -> None:
        skeleton = _skeleton("streamProcessor.ts")
        assert "yield { type: 'start'" not in skeleton
        assert "yield { type: 'end'" not in skeleton


# ---------------------------------------------------------------------------
# registry.ts — module-scope helpers, static factory methods, type aliases
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_class_present(self) -> None:
        assert "class Registry" in _skeleton("registry.ts")

    def test_static_methods_present(self) -> None:
        skeleton = _skeleton("registry.ts")
        assert "forRoot(" in skeleton
        assert "forTesting(" in skeleton

    def test_top_level_functions_present(self) -> None:
        skeleton = _skeleton("registry.ts")
        assert "function defineHandlers" in skeleton
        assert "function getToken" in skeleton

    def test_top_level_const_present(self) -> None:
        assert "ALL_HANDLERS" in _skeleton("registry.ts")

    def test_type_aliases_present(self) -> None:
        assert "HandlerOptions" in _skeleton("registry.ts")

    def test_no_implementation_lines(self) -> None:
        skeleton = _skeleton("registry.ts")
        assert "new Registry(" not in skeleton
        assert "Symbol(name)" not in skeleton
        assert "Object.values(" not in skeleton
