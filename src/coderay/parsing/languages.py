"""Language configuration: CST dispatch, skeleton, and chunking."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CstDispatchConfig:
    """Tree-sitter CST node-type sets for traversal, graph, and classification."""

    import_types: tuple[str, ...]
    function_scope_types: tuple[str, ...]
    class_scope_types: tuple[str, ...]
    decorator_scope_types: tuple[str, ...]
    call_types: tuple[str, ...]
    assignment_types: tuple[str, ...]
    decorator_types: tuple[str, ...]
    with_types: tuple[str, ...]


@dataclass
class SkeletonConfig:
    """Skeleton-only: docstrings and pass-through at module scope."""

    docstring_expr_type: str = "expression_statement"
    top_level_expr_types: tuple[str, ...] = ("expression_statement",)
    body_block_types: tuple[str, ...] = ("block", "statement_block")


@dataclass
class ChunkerConfig:
    """Which node types become embedding chunks."""

    chunk_types: tuple[str, ...]


class LanguageConfigProtocol(Protocol):
    """Contract for a supported language."""

    name: str
    extensions: tuple[str, ...]
    language_fn: Callable[[], Any]
    init_filenames: tuple[str, ...]
    cst: CstDispatchConfig
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


_PYTHON_CST_DISPATCH = CstDispatchConfig(
    import_types=(
        "import_statement",
        "import_from_statement",
        "future_import_statement",
    ),
    function_scope_types=("function_definition",),
    class_scope_types=("class_definition",),
    decorator_scope_types=("decorated_definition",),
    call_types=("call",),
    assignment_types=("assignment",),
    decorator_types=("decorator",),
    with_types=("with_statement",),
)


def _python_skeleton() -> SkeletonConfig:
    return SkeletonConfig(
        docstring_expr_type="expression_statement",
        top_level_expr_types=("expression_statement",),
        body_block_types=("block",),
    )


def _python_chunker() -> ChunkerConfig:
    return ChunkerConfig(
        chunk_types=(
            "function_definition",
            "class_definition",
            "decorated_definition",
        ),
    )


@dataclass
class PythonConfig:
    """Python language configuration."""

    name: str = "python"
    extensions: tuple[str, ...] = (".py", ".pyi")
    language_fn: Callable[[], Any] = _python_language
    init_filenames: tuple[str, ...] = ("__init__",)
    cst: CstDispatchConfig = field(default_factory=lambda: _PYTHON_CST_DISPATCH)
    skeleton: SkeletonConfig = field(default_factory=_python_skeleton)
    chunker: ChunkerConfig = field(default_factory=_python_chunker)


_JS_TS_IMPORT_TYPES: tuple[str, ...] = ("import_statement",)
_JS_TS_FUNCTION_SCOPE_TYPES: tuple[str, ...] = (
    "function_declaration",
    "method_definition",
    "arrow_function",
)
_JS_TS_CLASS_SCOPE_TYPES: tuple[str, ...] = (
    "class_declaration",
    "interface_declaration",  # not a class_* grammar node; same class-like dispatch
    "type_alias_declaration",  # same
    "type_declaration",  # same
)

_JS_TS_CST_DISPATCH = CstDispatchConfig(
    import_types=_JS_TS_IMPORT_TYPES,
    function_scope_types=_JS_TS_FUNCTION_SCOPE_TYPES,
    class_scope_types=_JS_TS_CLASS_SCOPE_TYPES,
    decorator_scope_types=(),
    call_types=("call_expression",),
    assignment_types=("assignment_expression", "variable_declarator"),
    decorator_types=(),
    with_types=(),
)


def _js_ts_skeleton() -> SkeletonConfig:
    return SkeletonConfig(
        docstring_expr_type="expression_statement",
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


@dataclass
class JavaScriptConfig:
    """JavaScript language configuration."""

    name: str = "javascript"
    extensions: tuple[str, ...] = (".js", ".jsx", ".mjs", ".cjs")
    language_fn: Callable[[], Any] = _javascript_language
    init_filenames: tuple[str, ...] = ("index",)
    cst: CstDispatchConfig = field(default_factory=lambda: _JS_TS_CST_DISPATCH)
    skeleton: SkeletonConfig = field(default_factory=_js_ts_skeleton)
    chunker: ChunkerConfig = field(default_factory=_js_ts_chunker)


@dataclass
class TypeScriptConfig:
    """TypeScript language configuration."""

    name: str = "typescript"
    extensions: tuple[str, ...] = (".ts", ".tsx")
    language_fn: Callable[[], Any] = _typescript_language
    init_filenames: tuple[str, ...] = ("index",)
    cst: CstDispatchConfig = field(default_factory=lambda: _JS_TS_CST_DISPATCH)
    skeleton: SkeletonConfig = field(default_factory=_js_ts_skeleton)
    chunker: ChunkerConfig = field(default_factory=_js_ts_chunker)


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
