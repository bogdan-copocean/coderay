"""Unified graph plugin wrapper (shared by all languages)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from coderay.core.models import GraphEdge, GraphNode
from coderay.graph.emit import emit_graph
from coderay.graph.facts import Fact
from coderay.graph.plugin_protocol import ProjectIndex
from coderay.parsing.base import ParserContext


class GraphPlugin:
    """Language graph pipeline: extract -> resolve -> emit."""

    def __init__(self, language_id: str, extractor_factory: Callable[..., Any]) -> None:
        """Initialize with language id and extractor constructor."""
        self.language_id = language_id
        self._extractor_factory = extractor_factory

    def extract_facts(
        self,
        ctx: ParserContext,
        *,
        module_index: dict[str, str],
    ) -> set[Fact]:
        """Lower CST to facts via language extractor."""
        result: set[Fact] = self._extractor_factory(
            ctx, module_index=module_index
        ).extract_facts_list()
        return result

    def resolve_facts(
        self, facts: Iterable[Fact], project: ProjectIndex
    ) -> Iterable[Fact]:
        """Patch facts before emit (no-op by default)."""
        return facts

    def emit(self, facts: Iterable[Fact]) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Convert facts to graph nodes and edges."""
        return emit_graph(facts)
