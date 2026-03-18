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
    import_source_field: str | None = None
    typed_param_types: tuple[str, ...] = ("typed_parameter",)


class LanguageConfigProtocol(Protocol):
    """Protocol for Tree-sitter language configuration."""

    name: str
    extensions: tuple[str, ...]
    language_fn: Callable[[], Any]
    graph: GraphConfig
    skeleton: SkeletonConfig
    chunker: ChunkerConfig


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
    name: str = "python"
    extensions: tuple[str, ...] = (".py", ".pyi")
    language_fn: Callable[[], Any] = _python_language
    import_types: tuple[str, ...] = (
        "import_statement",
        "import_from_statement",
        "future_import_statement",
    )
    function_scope_types: tuple[str, ...] = ("function_definition",)
    class_scope_types: tuple[str, ...] = ("class_definition",)
    decorator_scope_types: tuple[str, ...] = ("decorated_definition",)
    skeleton: SkeletonConfig = field(default_factory=SkeletonConfig)
    chunker: ChunkerConfig = field(
        default_factory=lambda: ChunkerConfig(
            chunk_types=(
                "function_definition",
                "class_definition",
                "decorated_definition",
            ),
        ),
    )
    graph: GraphConfig = field(
        default_factory=lambda: GraphConfig(call_types=("call",))
    )
    init_filenames: tuple[str, ...] = ("__init__",)


@dataclass
class JavaScriptConfig:
    name: str = "javascript"
    extensions: tuple[str, ...] = (".js", ".jsx", ".mjs", ".cjs")
    language_fn: Callable[[], Any] = _javascript_language
    import_types: tuple[str, ...] = ("import_statement",)
    function_scope_types: tuple[str, ...] = (
        "function_declaration",
        "method_definition",
    )
    class_scope_types: tuple[str, ...] = ("class_declaration",)
    decorator_scope_types: tuple[str, ...] = ()
    skeleton: SkeletonConfig = field(
        default_factory=lambda: SkeletonConfig(
            body_block_types=("statement_block",),
            top_level_expr_types=("expression_statement", "lexical_declaration"),
        ),
    )
    chunker: ChunkerConfig = field(
        default_factory=lambda: ChunkerConfig(
            chunk_types=(
                "function_declaration",
                "class_declaration",
                "method_definition",
                "arrow_function",
                "export_statement",
                "lexical_declaration",
            ),
        ),
    )
    graph: GraphConfig = field(
        default_factory=lambda: GraphConfig(
            call_types=("call_expression",),
            assignment_types=("assignment_expression", "variable_declarator"),
            import_source_field="source",
        ),
    )
    init_filenames: tuple[str, ...] = ("index",)


@dataclass
class TypeScriptConfig:
    name: str = "typescript"
    extensions: tuple[str, ...] = (".ts", ".tsx")
    language_fn: Callable[[], Any] = _typescript_language
    import_types: tuple[str, ...] = ("import_statement",)
    function_scope_types: tuple[str, ...] = (
        "function_declaration",
        "method_definition",
    )
    class_scope_types: tuple[str, ...] = ("class_declaration",)
    decorator_scope_types: tuple[str, ...] = ()
    skeleton: SkeletonConfig = field(
        default_factory=lambda: SkeletonConfig(
            extra_class_like_types=(
                "interface_declaration",
                "type_alias_declaration",
                "type_declaration",
            ),
            body_block_types=("statement_block",),
        ),
    )
    chunker: ChunkerConfig = field(
        default_factory=lambda: ChunkerConfig(
            chunk_types=(
                "function_declaration",
                "class_declaration",
                "method_definition",
                "arrow_function",
                "export_statement",
                "lexical_declaration",
                "interface_declaration",
                "type_alias_declaration",
            ),
        ),
    )
    graph: GraphConfig = field(
        default_factory=lambda: GraphConfig(
            call_types=("call_expression",),
            extra_class_scope_types=("interface_declaration",),
            assignment_types=("assignment_expression", "variable_declarator"),
            import_source_field="source",
            typed_param_types=(
                "typed_parameter",
                "required_parameter",
                "optional_parameter",
            ),
        ),
    )
    init_filenames: tuple[str, ...] = ("index",)


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


def get_init_filenames() -> set[str]:
    """Return init-style filenames (e.g. __init__, index)."""
    names: set[str] = set()
    for cfg in LANGUAGE_REGISTRY.values():
        names.update(cfg.init_filenames)
    return names


def get_resolution_suffixes() -> list[str]:
    """Return file suffixes for import resolution."""
    suffixes: list[str] = []
    seen: set[str] = set()
    for cfg in LANGUAGE_REGISTRY.values():
        for ext in cfg.extensions:
            if ext not in seen:
                suffixes.append(ext)
                seen.add(ext)
            for init in cfg.init_filenames:
                combo = f"/{init}{ext}"
                if combo not in seen:
                    suffixes.append(combo)
                    seen.add(combo)
    return suffixes
