"""Per-file graph extraction helpers and thin wrapper around GraphBuilder."""

from __future__ import annotations

from typing import Any

from coderay.graph._utils import resolve_relative_import
from coderay.graph.graph_builder import GraphBuilder
from coderay.graph.identifiers import file_path_to_module_names
from coderay.graph.types import ModuleIndex

__all__ = [
    "ModuleIndex",
    "_resolve_relative_import",
    "build_module_index",
    "extract_graph_from_file",
]

_resolve_relative_import = resolve_relative_import


def build_module_index(file_paths: list[str]) -> ModuleIndex:
    """Build module index mapping dotted module names to file paths."""
    module_index: ModuleIndex = {}
    for fp in file_paths:
        for mod_name in file_path_to_module_names(fp):
            # Stable pick: first path wins if the same module name appears twice.
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
    mi = module_index or {}
    return GraphBuilder(mi).process_file(file_path, content)
