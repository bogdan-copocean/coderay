"""Python graph plugin."""

from __future__ import annotations

from coderay.core.models import GraphEdge, GraphNode
from coderay.graph.emit import emit_graph
from coderay.graph.plugin_protocol import ProjectIndex
from coderay.graph.plugins.python.extractor import PythonGraphExtractor
from coderay.graph.registry import register_graph_plugin
from coderay.parsing.base import ParserContext


class PythonGraphPlugin:
    """Python language graph pipeline."""

    language_id = "python"

    def extract_facts(
        self,
        ctx: ParserContext,
        *,
        excluded_modules: frozenset[str],
        module_index: dict[str, str],
    ):
        return PythonGraphExtractor(
            ctx,
            excluded_modules=excluded_modules,
            module_index=module_index,
        ).extract_facts_list()

    def resolve_facts(self, facts, project: ProjectIndex):
        return facts

    def emit(self, facts) -> tuple[list[GraphNode], list[GraphEdge]]:
        return emit_graph(facts)


register_graph_plugin(PythonGraphPlugin())
