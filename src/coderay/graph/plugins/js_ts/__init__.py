"""JavaScript / TypeScript graph plugins (shared CST lowering)."""

from __future__ import annotations

from coderay.core.models import GraphEdge, GraphNode
from coderay.graph.emit import emit_graph
from coderay.graph.plugin_protocol import ProjectIndex
from coderay.graph.plugins.js_ts.extractor import JsTsGraphExtractor
from coderay.graph.registry import register_graph_plugin
from coderay.parsing.base import ParserContext


class JsTsGraphPlugin:
    """Shared pipeline for JavaScript and TypeScript."""

    def __init__(self, language_id: str) -> None:
        self.language_id = language_id

    def extract_facts(
        self,
        ctx: ParserContext,
        *,
        excluded_modules: frozenset[str],
        module_index: dict[str, str],
    ):
        return JsTsGraphExtractor(
            ctx,
            excluded_modules=excluded_modules,
            module_index=module_index,
        ).extract_facts_list()

    def resolve_facts(self, facts, project: ProjectIndex):
        return facts

    def emit(self, facts) -> tuple[list[GraphNode], list[GraphEdge]]:
        return emit_graph(facts)


register_graph_plugin(JsTsGraphPlugin("javascript"))
register_graph_plugin(JsTsGraphPlugin("typescript"))
