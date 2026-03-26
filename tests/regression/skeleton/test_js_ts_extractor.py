"""Tests for skeleton.extractor (canonical JS/TS concepts)."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.skeleton.extractor import extract_skeleton
from tests.regression.skeleton.conftest import (
    EXPECTED_TS_CANONICAL_WITH_IMPORTS,
    EXPECTED_TS_CANONICAL_WITHOUT_IMPORTS,
    EXPECTED_TS_SYMBOL_BUILD_PROFILE_LABEL,
    EXPECTED_TS_SYMBOL_CORESERVICE,
    EXPECTED_TS_SYMBOL_CORESERVICE_WITH_CLOSURE,
    EXPECTED_TS_SYMBOL_WRAPPER,
    EXPECTED_TS_UNKNOWN_SYMBOL_PREFIX,
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
        assert skeleton == EXPECTED_TS_CANONICAL_WITH_IMPORTS

    @pytest.mark.parametrize("path", [("test.xyz"), ("noext")])
    def test_unsupported_extension_returns_content_unchanged(self, path: str) -> None:
        _, content = self._canonical_content()
        assert extract_skeleton(path, content) == content

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("CoreService", EXPECTED_TS_SYMBOL_CORESERVICE),
            (
                "CoreService.withClosure",
                EXPECTED_TS_SYMBOL_CORESERVICE_WITH_CLOSURE,
            ),
            (
                "buildProfileLabel",
                EXPECTED_TS_SYMBOL_BUILD_PROFILE_LABEL,
            ),
        ],
    )
    def test_symbol_filter_matches_expected_output(
        self, symbol: str, expected: str
    ) -> None:
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol=symbol)
        assert skeleton == expected

    def test_without_imports_matches_expected_output(self) -> None:
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, include_imports=False)
        assert skeleton == EXPECTED_TS_CANONICAL_WITHOUT_IMPORTS

    @pytest.mark.parametrize("symbol", ["DoesNotExist"])
    def test_unknown_symbol_returns_hint(self, symbol: str) -> None:
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol=symbol)
        expected_prefix = EXPECTED_TS_UNKNOWN_SYMBOL_PREFIX.format(symbol=symbol)
        assert skeleton.startswith(expected_prefix)

    @pytest.mark.xfail(reason="Closure symbol retrieval not supported")
    def test_closure_wrapper_symbol_not_supported(self) -> None:
        path, content = self._canonical_content()
        skeleton = extract_skeleton(path, content, symbol="wrapper")
        assert skeleton == EXPECTED_TS_SYMBOL_WRAPPER
