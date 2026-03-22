"""Extract code graph (nodes, edges) from source via language plugins."""

from __future__ import annotations

import logging
from typing import Any

from coderay.core.config import get_config
from coderay.graph._utils import resolve_relative_import
from coderay.graph.file_context import FileContext
from coderay.graph.identifiers import file_path_to_module_names
from coderay.graph.plugin_protocol import ProjectIndex
from coderay.graph.registry import ensure_plugins_loaded, get_graph_plugin
from coderay.parsing.base import get_parse_context
from coderay.parsing.builtins import PYTHON_BUILTINS

__all__ = [
    "FileContext",
    "ModuleIndex",
    "PYTHON_BUILTINS",
    "_resolve_relative_import",
    "build_module_filter",
    "build_module_index",
    "extract_graph_from_file",
]

_resolve_relative_import = resolve_relative_import

logger = logging.getLogger(__name__)

_DEFAULT_EXCLUDED_MODULES: frozenset[str] = frozenset(
    {
        "builtins",
        "typing",
        "typing_extensions",
        "abc",
        "__future__",
    }
)

ModuleIndex = dict[str, str]


def build_module_index(file_paths: list[str]) -> ModuleIndex:
    """Build module index mapping dotted module names to file paths."""
    module_index: ModuleIndex = {}
    for fp in file_paths:
        for mod_name in file_path_to_module_names(fp):
            if mod_name not in module_index:
                module_index[mod_name] = fp
    return module_index


def build_module_filter() -> frozenset[str]:
    """Build the module exclusion set from defaults + application config."""
    config = get_config()
    extra_excludes = set(config.graph.exclude_modules or [])
    force_includes = set(config.graph.include_modules or [])
    return frozenset((_DEFAULT_EXCLUDED_MODULES | extra_excludes) - force_includes)


def extract_graph_from_file(
    file_path: str,
    content: str,
    *,
    excluded_modules: frozenset[str] | None = None,
    module_index: ModuleIndex | None = None,
) -> tuple[Any, Any]:
    """Parse a source file and extract all graph nodes and edges.

    Returns ``([], [])`` if the language is unsupported or parsing fails.
    """
    ensure_plugins_loaded()
    ctx = get_parse_context(file_path, content)
    if ctx is None:
        return [], []

    plugin = get_graph_plugin(ctx.lang_cfg.name)
    if plugin is None:
        return [], []

    if excluded_modules is None:
        excluded_modules = build_module_filter()

    mi = module_index or {}
    facts = plugin.extract_facts(
        ctx,
        excluded_modules=excluded_modules,
        module_index=mi,
    )
    facts = plugin.resolve_facts(facts, ProjectIndex(mi))
    return plugin.emit(facts)
