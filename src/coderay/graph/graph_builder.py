"""Multi-file graph extraction: dispatch, emit, merge into CodeGraph, post-merge."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from coderay.core.config import get_config
from coderay.core.models import GraphEdge, GraphNode
from coderay.graph.code_graph import CodeGraph
from coderay.graph.emit import emit_graph, filter_external_edges
from coderay.graph.facts import Fact
from coderay.graph.language_plugin import get_extractor
from coderay.graph.pipeline import run_post_merge_pipeline
from coderay.graph.types import ModuleIndex, ProjectIndex
from coderay.parsing.base import get_parse_context

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Module index, per-file extract/emit, graph merge, post-merge."""

    def __init__(self, module_index: ModuleIndex) -> None:
        self._module_index = module_index

    def resolve_facts(
        self, facts: Iterable[Fact], project: ProjectIndex
    ) -> Iterable[Fact]:
        """Hook before emit; default is identity."""
        del project
        return facts

    def process_file(
        self, file_path: str, content: str
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Parse one file and return graph nodes and edges."""
        ctx = get_parse_context(file_path, content)
        if ctx is None:
            return [], []
        ext_cls = get_extractor(ctx.lang_cfg.name)
        if ext_cls is None:
            return [], []
        facts = ext_cls(ctx, module_index=self._module_index).extract_facts_list()
        facts = self.resolve_facts(facts, ProjectIndex(self._module_index))
        nodes, edges = emit_graph(facts)
        if not get_config().graph.include_external:
            edges = filter_external_edges(edges, set(self._module_index.values()))
        return nodes, edges

    def build(self, file_paths_and_contents: list[tuple[str, str]]) -> CodeGraph:
        """Merge all files into a CodeGraph and run post-merge passes."""
        graph = CodeGraph()
        langs_seen: set[str] = set()

        for fp, content in file_paths_and_contents:
            try:
                ctx = get_parse_context(fp, content)
                if ctx is not None:
                    langs_seen.add(ctx.lang_cfg.name)
                nodes, edges = self.process_file(fp, content)
                graph.add_nodes_and_edges(nodes, edges)
            except Exception as exc:
                logger.exception("Graph extraction failed for %s: %s", fp, exc)
                raise

        rewritten, pruned = run_post_merge_pipeline(graph, langs=langs_seen)
        logger.info(
            "Graph built: %d nodes, %d edges (%d phantoms rewritten, %d pruned)",
            graph.node_count,
            graph.edge_count,
            rewritten,
            pruned,
        )
        return graph
