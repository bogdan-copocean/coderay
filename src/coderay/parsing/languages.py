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
    """Skeleton-specific configuration (fields not shared with other features)."""

    extra_class_like_types: tuple[str, ...] = ()
    top_level_expr_types: tuple[str, ...] = ("expression_statement",)
    export_like_types: tuple[str, ...] = ("export_statement", "lexical_declaration")


@dataclass
class ChunkerConfig:
    """Configuration for chunking for a language."""

    chunk_types: tuple[str, ...]


@dataclass
class GraphConfig:
    """Graph-specific configuration (fields not shared with other features)."""

    call_types: tuple[str, ...]
    extra_class_scope_types: tuple[str, ...] = ()


class LanguageConfigProtocol(Protocol):
    """Describe how a programming language is parsed with Tree-sitter.

    Shared node type sets (``import_types``, ``function_scope_types``,
    ``class_scope_types``) live here so that skeleton, graph, and future
    features reference the same definitions.  Feature-specific sub-configs
    carry only what is unique to that feature.
    """

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
    skeleton: SkeletonConfig = field(default_factory=SkeletonConfig)
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
        default_factory=lambda: GraphConfig(call_types=("call_expression",)),
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
    """Return the LanguageConfig for a file based on its extension, or None."""
    ext = Path(path).suffix.lower()
    lang_name = _EXTENSION_MAP.get(ext)
    if lang_name is None:
        return None
    return LANGUAGE_REGISTRY.get(lang_name)


def get_supported_extensions() -> set[str]:
    """Return all file extensions we can index."""
    return set(_EXTENSION_MAP.keys())


def get_init_filenames() -> set[str]:
    """Return all init-style filenames across languages (e.g. __init__, index)."""
    names: set[str] = set()
    for cfg in LANGUAGE_REGISTRY.values():
        names.update(cfg.init_filenames)
    return names


def get_resolution_suffixes() -> list[str]:
    """Return file suffixes for resolving import targets."""
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
