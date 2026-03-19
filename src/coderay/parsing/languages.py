"""Language configuration for Tree-sitter based analyzers.

Single source of truth for all language-specific AST node types, behavior
flags, and sub-configs consumed by chunking, skeleton extraction, and
graph building.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from coderay.parsing.builtins import JS_TS_BUILTINS, PYTHON_ALL_BUILTINS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-configs: each consumer (skeleton, chunker, graph) reads its own slice.
# ---------------------------------------------------------------------------


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
    """Graph-extraction-specific AST types and behavior flags.

    Shared fields (import_types, function_scope_types, class_scope_types)
    live on the base language config; this holds the *extras* that only
    the graph extractor needs.
    """

    call_types: tuple[str, ...]
    assignment_types: tuple[str, ...] = ("assignment",)
    class_body_types: tuple[str, ...] = ("block",)
    typed_param_types: tuple[str, ...] = ("typed_parameter",)
    extra_class_scope_types: tuple[str, ...] = ()
    builtins: frozenset[str] = field(default_factory=frozenset)
    # "self." for Python, "this." for JS/TS, "" when N/A
    self_prefix: str = ""
    super_prefixes: tuple[str, ...] = ("super().", "super.")
    # Tuple-based dispatch: empty tuple = feature disabled for this language.
    decorator_types: tuple[str, ...] = ()
    with_types: tuple[str, ...] = ()
    tracks_property_types: bool = False


# ---------------------------------------------------------------------------
# Protocol — structural contract for all language configs.
# ---------------------------------------------------------------------------


class LanguageConfigProtocol(Protocol):
    """Structural contract for language configs.

    Every language provides shared AST node types and domain-specific
    sub-configs for skeleton, chunker, and graph extraction.
    """

    name: str
    extensions: tuple[str, ...]
    language_fn: Callable[[], Any]
    init_filenames: tuple[str, ...]
    import_types: tuple[str, ...]
    function_scope_types: tuple[str, ...]
    class_scope_types: tuple[str, ...]
    decorator_scope_types: tuple[str, ...]
    skeleton: SkeletonConfig
    chunker: ChunkerConfig
    graph: GraphConfig


# ---------------------------------------------------------------------------
# Language function loaders (lazy imports to avoid heavy deps at import time).
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Concrete language configs.
# ---------------------------------------------------------------------------


@dataclass
class PythonConfig:
    """Python language configuration."""

    name: str = "python"
    extensions: tuple[str, ...] = (".py", ".pyi")
    language_fn: Callable[[], Any] = _python_language
    init_filenames: tuple[str, ...] = ("__init__",)
    import_types: tuple[str, ...] = (
        "import_statement",
        "import_from_statement",
        "future_import_statement",
    )
    function_scope_types: tuple[str, ...] = ("function_definition",)
    class_scope_types: tuple[str, ...] = ("class_definition",)
    decorator_scope_types: tuple[str, ...] = ("decorated_definition",)
    skeleton: SkeletonConfig = field(
        default_factory=lambda: SkeletonConfig(
            body_block_types=("block",),
        ),
    )
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
        default_factory=lambda: GraphConfig(
            call_types=("call",),
            builtins=PYTHON_ALL_BUILTINS,
            self_prefix="self.",
            decorator_types=("decorator",),
            with_types=("with_statement",),
            tracks_property_types=True,
        ),
    )


# JS and TS share AST structure; only extensions and language_fn differ.


def _js_ts_skeleton() -> SkeletonConfig:
    return SkeletonConfig(
        extra_class_like_types=(
            "interface_declaration",
            "type_alias_declaration",
            "type_declaration",
        ),
        top_level_expr_types=("expression_statement", "lexical_declaration"),
        body_block_types=("statement_block",),
    )


def _js_ts_chunker() -> ChunkerConfig:
    return ChunkerConfig(
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
    )


def _js_ts_graph() -> GraphConfig:
    return GraphConfig(
        call_types=("call_expression",),
        assignment_types=("assignment_expression", "variable_declarator"),
        class_body_types=("block", "class_body"),
        typed_param_types=(
            "typed_parameter",
            "required_parameter",
            "optional_parameter",
        ),
        extra_class_scope_types=("interface_declaration",),
        builtins=JS_TS_BUILTINS,
        self_prefix="this.",
    )


_JS_TS_IMPORT_TYPES: tuple[str, ...] = ("import_statement",)
_JS_TS_FUNCTION_SCOPE_TYPES: tuple[str, ...] = (
    "function_declaration",
    "method_definition",
    "arrow_function",
)
_JS_TS_CLASS_SCOPE_TYPES: tuple[str, ...] = ("class_declaration",)


@dataclass
class JavaScriptConfig:
    """JavaScript language configuration."""

    name: str = "javascript"
    extensions: tuple[str, ...] = (".js", ".jsx", ".mjs", ".cjs")
    language_fn: Callable[[], Any] = _javascript_language
    init_filenames: tuple[str, ...] = ("index",)
    import_types: tuple[str, ...] = _JS_TS_IMPORT_TYPES
    function_scope_types: tuple[str, ...] = _JS_TS_FUNCTION_SCOPE_TYPES
    class_scope_types: tuple[str, ...] = _JS_TS_CLASS_SCOPE_TYPES
    decorator_scope_types: tuple[str, ...] = ()
    skeleton: SkeletonConfig = field(default_factory=_js_ts_skeleton)
    chunker: ChunkerConfig = field(default_factory=_js_ts_chunker)
    graph: GraphConfig = field(default_factory=_js_ts_graph)


@dataclass
class TypeScriptConfig:
    """TypeScript language configuration."""

    name: str = "typescript"
    extensions: tuple[str, ...] = (".ts", ".tsx")
    language_fn: Callable[[], Any] = _typescript_language
    init_filenames: tuple[str, ...] = ("index",)
    import_types: tuple[str, ...] = _JS_TS_IMPORT_TYPES
    function_scope_types: tuple[str, ...] = _JS_TS_FUNCTION_SCOPE_TYPES
    class_scope_types: tuple[str, ...] = _JS_TS_CLASS_SCOPE_TYPES
    decorator_scope_types: tuple[str, ...] = ()
    skeleton: SkeletonConfig = field(default_factory=_js_ts_skeleton)
    chunker: ChunkerConfig = field(default_factory=_js_ts_chunker)
    graph: GraphConfig = field(default_factory=_js_ts_graph)


# ---------------------------------------------------------------------------
# Registry and lookups.
# ---------------------------------------------------------------------------

LANGUAGE_REGISTRY: dict[str, LanguageConfigProtocol] = {
    "python": PythonConfig(),
    "javascript": JavaScriptConfig(),
    "typescript": TypeScriptConfig(),
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
