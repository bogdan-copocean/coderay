"""Tests for skeleton.extractor (canonical JS/TS concepts)."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.skeleton.extractor import extract_skeleton
from tests.regression.skeleton.conftest import (
    EXPECTED_TS_SYMBOL_WRAPPER,
    EXPECTED_UNKNOWN_SYMBOL_PREFIX,
    load_skeleton_fixture,
)

CANONICAL = Path(__file__).with_name("canonical_concepts.ts")


class TestCanonicalConcepts:
    @staticmethod
    def _canonical_content() -> tuple[str, str]:
        """Return canonical file path and content."""
        return str(CANONICAL), CANONICAL.read_text(encoding="utf-8")

    def test_canonical_concepts_skeleton(self) -> None:
        """Verify skeleton extraction for canonical JS/TS concepts."""
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, include_imports=True)
        assert skeleton == load_skeleton_fixture(
            "ts_with_imports.expected", canonical="ts"
        )

    @pytest.mark.parametrize("path", [("test.xyz"), ("noext")])
    def test_unsupported_extension_returns_content_unchanged(self, path: str) -> None:
        _, content = self._canonical_content()
        assert extract_skeleton(path, content) == content

    @pytest.mark.parametrize(
        "symbol,fixture",
        [
            ("CoreService", "ts_symbol_CoreService.expected"),
            ("CoreService.withClosure", "ts_symbol_CoreService_withClosure.expected"),
            ("buildProfileLabel", "ts_symbol_buildProfileLabel.expected"),
        ],
    )
    def test_symbol_filter_matches_expected_output(
        self, symbol: str, fixture: str
    ) -> None:
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol=symbol)
        assert skeleton == load_skeleton_fixture(fixture, canonical="ts")

    def test_without_imports_matches_expected_output(self) -> None:
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, include_imports=False)
        assert skeleton == load_skeleton_fixture(
            "ts_without_imports.expected", canonical="ts"
        )

    @pytest.mark.parametrize("symbol", ["DoesNotExist"])
    def test_unknown_symbol_returns_hint(self, symbol: str) -> None:
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol=symbol)
        expected_prefix = EXPECTED_UNKNOWN_SYMBOL_PREFIX.format(symbol=symbol)
        assert skeleton.startswith(expected_prefix)

    @pytest.mark.xfail(reason="Closure symbol retrieval not supported")
    def test_closure_wrapper_symbol_not_supported(self) -> None:
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol="wrapper")
        assert skeleton == EXPECTED_TS_SYMBOL_WRAPPER
