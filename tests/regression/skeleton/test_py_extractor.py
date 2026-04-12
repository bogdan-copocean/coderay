"""Tests for skeleton.extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.skeleton.extractor import extract_skeleton
from tests.regression.skeleton.conftest import (
    EXPECTED_PY_CANONICAL_SYMBOL_WRAPPER,
    EXPECTED_UNKNOWN_SYMBOL_PREFIX,
    load_skeleton_fixture,
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
        assert skeleton == load_skeleton_fixture(
            "py_with_imports.expected", canonical="py"
        )

    @pytest.mark.parametrize("path", [("test.xyz"), ("noext")])
    def test_unsupported_extension_returns_content_unchanged(self, path):
        _, content = self._canonical_content()
        assert extract_skeleton(path, content) == content

    def test_without_imports_matches_expected_output(self):
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, include_imports=False)
        assert skeleton == load_skeleton_fixture(
            "py_without_imports.expected", canonical="py"
        )

    @pytest.mark.parametrize(
        "symbol,fixture",
        [
            ("Repository", "py_symbol_Repository.expected"),
            ("Repository.get", "py_symbol_Repository_get.expected"),
            ("local_imports_example", "py_symbol_local_imports_example.expected"),
            ("decorator", "py_symbol_decorator.expected"),
        ],
    )
    def test_symbol_filter_matches_expected_output(self, symbol: str, fixture: str):
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol=symbol)
        assert skeleton == load_skeleton_fixture(fixture, canonical="py")

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
