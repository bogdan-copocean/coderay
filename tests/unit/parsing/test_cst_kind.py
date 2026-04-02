"""Tests for shared CST node classification."""

import pytest

from coderay.parsing.cst_kind import TraversalKind, classify_node
from coderay.parsing.languages import LANGUAGE_REGISTRY


@pytest.mark.parametrize(
    "lang,ntype,expected",
    [
        ("python", "module", TraversalKind.MODULE),
        ("python", "import_statement", TraversalKind.IMPORT),
        ("python", "function_definition", TraversalKind.FUNCTION),
        ("python", "class_definition", TraversalKind.CLASS),
        ("python", "call", TraversalKind.CALL),
        ("python", "decorator", TraversalKind.DECORATOR),
        ("python", "assignment", TraversalKind.ASSIGNMENT),
        ("python", "with_statement", TraversalKind.WITH),
        ("python", "decorated_definition", TraversalKind.DECORATED_DEFINITION),
        ("python", "pass", TraversalKind.OTHER),
        ("javascript", "import_statement", TraversalKind.IMPORT),
        ("javascript", "class_declaration", TraversalKind.CLASS),
        ("javascript", "interface_declaration", TraversalKind.CLASS),
        ("javascript", "expression_statement", TraversalKind.OTHER),
    ],
)
def test_classify_node(lang, ntype, expected):
    """Kinds match node type via ``LanguageConfig.cst``."""
    cfg = LANGUAGE_REGISTRY[lang]
    assert classify_node(ntype, cfg) == expected


def test_skeleton_structural_matches_classify():
    """Types skeleton treats as structural are not OTHER."""
    cfg = LANGUAGE_REGISTRY["python"]
    dispatch = cfg.cst
    for ntype in (
        "module",
        *dispatch.import_types,
        *dispatch.function_scope_types,
        *dispatch.class_scope_types,
        *dispatch.decorator_scope_types,
    ):
        assert classify_node(ntype, cfg) != TraversalKind.OTHER
