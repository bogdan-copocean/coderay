"""Multi-language registry for tree-sitter parsers and chunk/graph configs.

Each supported language defines its file extensions, tree-sitter grammar loader,
and the AST node types used for chunking and graph extraction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)


@dataclass
class LanguageConfig:
    """Configuration for a single language."""

    name: str
    extensions: tuple[str, ...]
    language_fn: Callable[[], Any]
    chunk_types: tuple[str, ...]
    scope_types: tuple[str, ...] = ("function_definition", "class_definition")
    import_types: tuple[str, ...] = ("import_statement", "import_from_statement")

    def get_parser(self) -> Parser:
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
    chunk_types=(
        "function_definition",
        "class_definition",
        "decorated_definition",
    ),
    scope_types=("function_definition", "class_definition"),
    import_types=("import_statement", "import_from_statement"),
)

JAVASCRIPT_CONFIG = LanguageConfig(
    name="javascript",
    extensions=(".js", ".jsx", ".mjs", ".cjs"),
    language_fn=_javascript_language,
    chunk_types=(
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
        "lexical_declaration",
    ),
    scope_types=("function_declaration", "class_declaration", "method_definition"),
    import_types=("import_statement",),
)

TYPESCRIPT_CONFIG = LanguageConfig(
    name="typescript",
    extensions=(".ts", ".tsx"),
    language_fn=_typescript_language,
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
    scope_types=(
        "function_declaration",
        "class_declaration",
        "method_definition",
        "interface_declaration",
    ),
    import_types=("import_statement",),
)

GO_CONFIG = LanguageConfig(
    name="go",
    extensions=(".go",),
    language_fn=_go_language,
    chunk_types=(
        "function_declaration",
        "method_declaration",
        "type_declaration",
    ),
    scope_types=("function_declaration", "method_declaration"),
    import_types=("import_declaration",),
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
