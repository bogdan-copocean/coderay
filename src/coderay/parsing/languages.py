from __future__ import annotations

"""Language configuration for Tree-sitter based analyzers.

This module centralizes language-specific configuration used by all Tree-sitter
consumers (chunking, skeleton extraction, graph building, etc.).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkeletonConfig:
    """Configuration for skeleton extraction for a language."""

    import_types: tuple[str, ...]
    function_scope_types: tuple[str, ...]
    class_scope_types: tuple[str, ...]
    extra_class_like_types: tuple[str, ...] = ()
    top_level_expr_types: tuple[str, ...] = ("expression_statement",)
    export_like_types: tuple[str, ...] = ("export_statement", "lexical_declaration")


@dataclass
class ChunkerConfig:
    """Configuration for chunking for a language."""

    chunk_types: tuple[str, ...]


@dataclass
class GraphConfig:
    """Configuration for graph extraction for a language."""

    import_types: tuple[str, ...]
    call_types: tuple[str, ...]
    function_scope_types: tuple[str, ...]
    class_scope_types: tuple[str, ...]


@dataclass
class LanguageConfig:
    """Describe how a programming language is parsed with Tree-sitter.

    Per-language container that holds feature-specific sub-configs.
    """

    name: str
    extensions: tuple[str, ...]
    language_fn: Callable[[], Any]
    skeleton: SkeletonConfig
    chunker: ChunkerConfig
    graph: GraphConfig
    init_filenames: tuple[str, ...] = ()

    def get_parser(self):
        """Create and return a Tree-sitter Parser for this language."""
        from tree_sitter import Language, Parser

        lang = Language(self.language_fn())
        parser = Parser(lang)
        return parser


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


PYTHON_CONFIG = LanguageConfig(
    name="python",
    extensions=(".py", ".pyi"),
    language_fn=_python_language,
    skeleton=SkeletonConfig(
        import_types=("import_statement", "import_from_statement"),
        function_scope_types=("function_definition",),
        class_scope_types=("class_definition",),
    ),
    chunker=ChunkerConfig(
        chunk_types=(
            "function_definition",
            "class_definition",
            "decorated_definition",
        ),
    ),
    graph=GraphConfig(
        import_types=("import_statement", "import_from_statement"),
        call_types=("call",),
        function_scope_types=("function_definition",),
        class_scope_types=("class_definition",),
    ),
    init_filenames=("__init__",),
)

JAVASCRIPT_CONFIG = LanguageConfig(
    name="javascript",
    extensions=(".js", ".jsx", ".mjs", ".cjs"),
    language_fn=_javascript_language,
    skeleton=SkeletonConfig(
        import_types=("import_statement",),
        function_scope_types=("function_declaration", "method_definition"),
        class_scope_types=("class_declaration",),
        extra_class_like_types=(),
        top_level_expr_types=("expression_statement",),
        export_like_types=("export_statement", "lexical_declaration"),
    ),
    chunker=ChunkerConfig(
        chunk_types=(
            "function_declaration",
            "class_declaration",
            "method_definition",
            "arrow_function",
            "export_statement",
            "lexical_declaration",
        ),
    ),
    graph=GraphConfig(
        import_types=("import_statement",),
        call_types=("call_expression",),
        function_scope_types=("function_declaration", "method_definition"),
        class_scope_types=("class_declaration",),
    ),
    init_filenames=("index",),
)

TYPESCRIPT_CONFIG = LanguageConfig(
    name="typescript",
    extensions=(".ts", ".tsx"),
    language_fn=_typescript_language,
    skeleton=SkeletonConfig(
        import_types=("import_statement",),
        function_scope_types=("function_declaration", "method_definition"),
        class_scope_types=("class_declaration",),
        extra_class_like_types=(
            "interface_declaration",
            "type_alias_declaration",
            "type_declaration",
        ),
        top_level_expr_types=("expression_statement",),
        export_like_types=("export_statement", "lexical_declaration"),
    ),
    chunker=ChunkerConfig(
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
    graph=GraphConfig(
        import_types=("import_statement",),
        call_types=("call_expression",),
        function_scope_types=("function_declaration", "method_definition"),
        class_scope_types=("class_declaration", "interface_declaration"),
    ),
    init_filenames=("index",),
)

GO_CONFIG = LanguageConfig(
    name="go",
    extensions=(".go",),
    language_fn=_go_language,
    skeleton=SkeletonConfig(
        import_types=("import_declaration",),
        function_scope_types=("function_declaration", "method_declaration"),
        class_scope_types=(),
        extra_class_like_types=("type_declaration",),
    ),
    chunker=ChunkerConfig(
        chunk_types=(
            "function_declaration",
            "method_declaration",
            "type_declaration",
        ),
    ),
    graph=GraphConfig(
        import_types=("import_declaration",),
        call_types=("call_expression",),
        function_scope_types=("function_declaration", "method_declaration"),
        class_scope_types=(),
    ),
    init_filenames=(),
)


LANGUAGE_REGISTRY: dict[str, LanguageConfig] = {
    "python": PYTHON_CONFIG,
    "javascript": JAVASCRIPT_CONFIG,
    "typescript": TYPESCRIPT_CONFIG,
    "go": GO_CONFIG,
}

_EXTENSION_MAP: dict[str, str] = {}
for _lang_name, _cfg in LANGUAGE_REGISTRY.items():
    for _ext in _cfg.extensions:
        _EXTENSION_MAP[_ext] = _lang_name


def get_language_for_file(path: str | Path) -> LanguageConfig | None:
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
