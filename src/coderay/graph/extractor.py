"""Extract code graph (nodes, edges) from source via language plugins."""

from __future__ import annotations

import logging
from typing import Any

from coderay.core.config import get_config
from coderay.graph._utils import resolve_relative_import
from coderay.graph.emit import filter_external_edges
from coderay.graph.file_context import FileContext
from coderay.graph.identifiers import file_path_to_module_names
from coderay.graph.plugin_protocol import ProjectIndex
from coderay.graph.registry import ensure_plugins_loaded, get_graph_plugin
from coderay.parsing.base import get_parse_context

__all__ = [
    "FileContext",
    "ModuleIndex",
    "_resolve_relative_import",
    "build_module_index",
    "extract_graph_from_file",
]

_resolve_relative_import = resolve_relative_import

logger = logging.getLogger(__name__)

ModuleIndex = dict[str, str]


def build_module_index(file_paths: list[str]) -> ModuleIndex:
    """Build module index mapping dotted module names to file paths."""
    module_index: ModuleIndex = {}
    for fp in file_paths:
        for mod_name in file_path_to_module_names(fp):
            if mod_name not in module_index:
                module_index[mod_name] = fp
    return module_index


def extract_graph_from_file(
    file_path: str,
    content: str,
    *,
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

    mi = module_index or {}
    facts = plugin.extract_facts(ctx, module_index=mi)
    facts = plugin.resolve_facts(facts, ProjectIndex(mi))
    nodes, edges = plugin.emit(facts)
    if not get_config().graph.include_external:
        edges = filter_external_edges(edges, set(mi.values()))
    return nodes, edges
