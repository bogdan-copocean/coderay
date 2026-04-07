"""Language plugin registry: extractor class + post-merge passes per language."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from coderay.graph.code_graph import CodeGraph

if TYPE_CHECKING:
    from coderay.graph.extractors.base import BaseGraphExtractor


@dataclass
class LanguagePlugin:
    """Everything needed to support one language in the graph pipeline."""

    lang_name: str
    extractor_cls: type[BaseGraphExtractor]
    post_merge_passes: Callable[[CodeGraph], tuple[int, int]] | None = field(
        default=None
    )


_REGISTRY: dict[str, LanguagePlugin] = {}


def register(plugin: LanguagePlugin) -> None:
    """Register a language plugin. Called from each language's __init__.py."""
    _REGISTRY[plugin.lang_name] = plugin


def get_extractor(lang_name: str) -> type[BaseGraphExtractor] | None:
    """Return the extractor class for a language, or None if unsupported."""
    plugin = _REGISTRY.get(lang_name)
    return plugin.extractor_cls if plugin else None


def run_passes(lang_name: str, graph: CodeGraph) -> tuple[int, int]:
    """Run post-merge passes for a language; return (rewritten, pruned)."""
    plugin = _REGISTRY.get(lang_name)
    if plugin and plugin.post_merge_passes:
        return plugin.post_merge_passes(graph)
    return 0, 0


def registered_languages() -> list[str]:
    """Return names of all registered languages."""
    return list(_REGISTRY.keys())
