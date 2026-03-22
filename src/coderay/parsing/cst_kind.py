"""Shared CST node classification (uses ``LanguageConfig.cst``)."""

from __future__ import annotations

from enum import Enum
from typing import Any


class TraversalKind(str, Enum):
    """High-level role of a syntax node; ordering matches graph extractors."""

    MODULE = "module"
    IMPORT = "import"
    FUNCTION = "function"
    CLASS = "class"
    CALL = "call"
    DECORATOR = "decorator"
    ASSIGNMENT = "assignment"
    WITH = "with"
    DECORATED_DEFINITION = "decorated_definition"
    OTHER = "other"


def classify_node(ntype: str, lang_cfg: Any) -> TraversalKind:
    """Classify a tree-sitter node type using ``lang_cfg.cst``."""
    if ntype == "module":
        return TraversalKind.MODULE
    dispatch = lang_cfg.cst
    if ntype in dispatch.import_types:
        return TraversalKind.IMPORT
    if ntype in dispatch.function_scope_types:
        return TraversalKind.FUNCTION

    if ntype in dispatch.class_scope_types:
        return TraversalKind.CLASS

    if ntype in dispatch.call_types:
        return TraversalKind.CALL
    if ntype in dispatch.decorator_types:
        return TraversalKind.DECORATOR
    if ntype in dispatch.assignment_types:
        return TraversalKind.ASSIGNMENT
    if ntype in dispatch.with_types:
        return TraversalKind.WITH
    if ntype in dispatch.decorator_scope_types:
        return TraversalKind.DECORATED_DEFINITION

    return TraversalKind.OTHER
