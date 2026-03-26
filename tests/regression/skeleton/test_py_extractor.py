"""Tests for skeleton.extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.skeleton.extractor import extract_skeleton
from tests.regression.skeleton.conftest import (
    EXPECTED_PY_CANONICAL_SYMBOL_FUNCTION_WITH_CLOSURE,
    EXPECTED_PY_CANONICAL_SYMBOL_LOCAL_IMPORTS,
    EXPECTED_PY_CANONICAL_SYMBOL_REPOSITORY,
    EXPECTED_PY_CANONICAL_SYMBOL_REPOSITORY_GET,
    EXPECTED_PY_CANONICAL_SYMBOL_WRAPPER,
    EXPECTED_PY_CANONICAL_WITH_IMPORTS,
    EXPECTED_PY_CANONICAL_WITHOUT_IMPORTS,
    EXPECTED_UNKNOWN_SYMBOL_PREFIX,
)

CANONICAL = Path(__file__).with_name("canonical_concepts.py")


class TestExtractSkeleton:
    @staticmethod
    def _canonical_content() -> tuple[str, str]:
        """Return canonical file path and content."""
        return str(CANONICAL), CANONICAL.read_text(encoding="utf-8")

    def test_canonical_concepts_skeleton(self):
        """Verify skeleton extraction for canonical Python concepts."""
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, include_imports=True)
        assert skeleton == EXPECTED_PY_CANONICAL_WITH_IMPORTS

    @pytest.mark.parametrize("path", [("test.xyz"), ("noext")])
    def test_unsupported_extension_returns_content_unchanged(self, path):
        _, content = self._canonical_content()
        assert extract_skeleton(path, content) == content

    def test_without_imports_matches_expected_output(self):
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, include_imports=False)
        assert skeleton == EXPECTED_PY_CANONICAL_WITHOUT_IMPORTS

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("Repository", EXPECTED_PY_CANONICAL_SYMBOL_REPOSITORY),
            ("Repository.get", EXPECTED_PY_CANONICAL_SYMBOL_REPOSITORY_GET),
            ("local_imports_example", EXPECTED_PY_CANONICAL_SYMBOL_LOCAL_IMPORTS),
            ("decorator", EXPECTED_PY_CANONICAL_SYMBOL_FUNCTION_WITH_CLOSURE),
        ],
    )
    def test_symbol_filter_matches_expected_output(self, symbol: str, expected: str):
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol=symbol)
        assert skeleton == expected

    @pytest.mark.parametrize("symbol", [("DoesNotExist"), ("FakeClass.method")])
    def test_unknown_symbol_returns_hint(self, symbol: str):
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol=symbol)
        expected_prefix = EXPECTED_UNKNOWN_SYMBOL_PREFIX.format(symbol=symbol)
        assert skeleton.startswith(expected_prefix)

    @pytest.mark.xfail(reason="Closure symbol retrieval not supported yet")
    def test_closure_wrapper_symbol_not_supported(self):
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol="wrapper")
        assert skeleton == EXPECTED_PY_CANONICAL_SYMBOL_WRAPPER
