"""Post-merge: rewrite bare-name phantom CALLS when uniquely resolvable repo-wide."""

from __future__ import annotations

import logging

from coderay.core.models import EdgeKind, GraphEdge
from coderay.graph.code_graph import CodeGraph

logger = logging.getLogger(__name__)


def rewrite_bare_phantom_calls(graph: CodeGraph) -> int:
    """Rewrite bare CALLS targets when ``resolve_symbol`` yields one node id."""
    rewritten = 0
    to_rewrite: list[tuple[str, str, str]] = []

    for u, v, _ in graph.iter_edges():
        if not graph.edge_has_kind(u, v, EdgeKind.CALLS):
            continue
        if graph.get_node(v) is not None:
            continue
        if "::" in v or "." in v:
            continue
        if graph.has_ambiguous_symbol(v):
            continue
        resolved = graph.resolve_symbol(v)
        if not resolved or resolved == v:
            continue
        if graph.get_node(resolved) is None:
            continue
        to_rewrite.append((u, v, resolved))

    for u, v, new_target in to_rewrite:
        graph.remove_edge(u, v, kind=EdgeKind.CALLS)
        graph.add_edge(GraphEdge(source=u, target=new_target, kind=EdgeKind.CALLS))
        rewritten += 1

    if rewritten:
        logger.info("Rewrote %d bare phantom CALLS", rewritten)
    return rewritten
