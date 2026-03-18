from __future__ import annotations

"""Language configuration for Tree-sitter based analyzers.

This module centralizes language-specific configuration used by all Tree-sitter
consumers (chunking, skeleton extraction, graph building, etc.).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class SkeletonConfig:
    """Skeleton-specific configuration."""

    extra_class_like_types: tuple[str, ...] = ()
    top_level_expr_types: tuple[str, ...] = ("expression_statement",)
    export_like_types: tuple[str, ...] = ("export_statement", "lexical_declaration")
    body_block_types: tuple[str, ...] = ("block", "statement_block")
    docstring_expr_type: str = "expression_statement"


@dataclass
class ChunkerConfig:
    """Chunking configuration per language."""

    chunk_types: tuple[str, ...]


@dataclass
class GraphConfig:
    """Graph-specific configuration."""

    call_types: tuple[str, ...]
    extra_class_scope_types: tuple[str, ...] = ()
    assignment_types: tuple[str, ...] = ("assignment",)
    class_body_types: tuple[str, ...] = ("block",)
    import_source_field: str | None = None
    typed_param_types: tuple[str, ...] = ("typed_parameter",)


class LanguageConfigProtocol(Protocol):
    """Protocol for Tree-sitter language configuration.

    Plugin languages (Python, JS, TS) have minimal config; graph, skeleton,
    chunker are None. Fallback languages (Go) have full config.
    """

    name: str
    extensions: tuple[str, ...]
    language_fn: Callable[[], Any]
    init_filenames: tuple[str, ...]
    graph: GraphConfig | None
    skeleton: SkeletonConfig | None
    chunker: ChunkerConfig | None


def _python_language():
    import tree_sitter_python as tspython

    return tspython.language()


def _javascript_language():
    import tree_sitter_javascript as tsjs

    return tsjs.language()


def _typescript_language():
    import tree_sitter_typescript as tsts

    if hasattr(tsts, "language_typescript"):
        return tsts.language_typescript()
    return tsts.language()


def _go_language():
    import tree_sitter_go as tsgo

    return tsgo.language()


@dataclass
class PythonConfig:
    """Minimal config for Python; plugins provide chunking, skeleton, graph."""

    name: str = "python"
    extensions: tuple[str, ...] = (".py", ".pyi")
    language_fn: Callable[[], Any] = _python_language
    init_filenames: tuple[str, ...] = ("__init__",)
    graph: GraphConfig | None = None
    skeleton: SkeletonConfig | None = None
    chunker: ChunkerConfig | None = None


@dataclass
class JavaScriptConfig:
    """Minimal config for JavaScript; plugins provide chunking, skeleton, graph."""

    name: str = "javascript"
    extensions: tuple[str, ...] = (".js", ".jsx", ".mjs", ".cjs")
    language_fn: Callable[[], Any] = _javascript_language
    init_filenames: tuple[str, ...] = ("index",)
    graph: GraphConfig | None = None
    skeleton: SkeletonConfig | None = None
    chunker: ChunkerConfig | None = None


@dataclass
class TypeScriptConfig:
    """Minimal config for TypeScript; plugins provide chunking, skeleton, graph."""

    name: str = "typescript"
    extensions: tuple[str, ...] = (".ts", ".tsx")
    language_fn: Callable[[], Any] = _typescript_language
    init_filenames: tuple[str, ...] = ("index",)
    graph: GraphConfig | None = None
    skeleton: SkeletonConfig | None = None
    chunker: ChunkerConfig | None = None


@dataclass
class GoConfig:
    name: str = "go"
    extensions: tuple[str, ...] = (".go",)
    language_fn: Callable[[], Any] = _go_language
    import_types: tuple[str, ...] = ("import_declaration",)
    function_scope_types: tuple[str, ...] = (
        "function_declaration",
        "method_declaration",
    )
    class_scope_types: tuple[str, ...] = ()
    decorator_scope_types: tuple[str, ...] = ()
    skeleton: SkeletonConfig = field(
        default_factory=lambda: SkeletonConfig(
            extra_class_like_types=("type_declaration",),
        ),
    )
    chunker: ChunkerConfig = field(
        default_factory=lambda: ChunkerConfig(
            chunk_types=(
                "function_declaration",
                "method_declaration",
                "type_declaration",
            ),
        ),
    )
    graph: GraphConfig = field(
        default_factory=lambda: GraphConfig(call_types=("call_expression",)),
    )
    init_filenames: tuple[str, ...] = ()


LANGUAGE_REGISTRY: dict[str, LanguageConfigProtocol] = {
    "python": PythonConfig(),
    "javascript": JavaScriptConfig(),
    "typescript": TypeScriptConfig(),
    "go": GoConfig(),
}

_EXTENSION_MAP: dict[str, str] = {}
for _lang_name, _cfg in LANGUAGE_REGISTRY.items():
    for _ext in _cfg.extensions:
        _EXTENSION_MAP[_ext] = _lang_name


def get_language_for_file(path: str | Path) -> LanguageConfigProtocol | None:
    """Return LanguageConfig for file by extension; None if unsupported."""
    ext = Path(path).suffix.lower()
    lang_name = _EXTENSION_MAP.get(ext)
    if lang_name is None:
        return None
    return LANGUAGE_REGISTRY.get(lang_name)


def get_supported_extensions() -> set[str]:
    """Return supported file extensions."""
    return set(_EXTENSION_MAP.keys())
