"""Python-specific post-merge passes on CodeGraph."""

from __future__ import annotations

import logging

from coderay.core.models import EdgeKind, GraphEdge
from coderay.graph.code_graph import CodeGraph

logger = logging.getLogger(__name__)


def run_python_passes(graph: CodeGraph) -> tuple[int, int]:
    """Rewrite package phantoms then prune ambiguous/unresolvable CALLS."""
    rewritten = _rewrite_package_phantom_targets(graph)
    pruned = _prune_phantom_calls(graph)
    return rewritten, pruned


def _rewrite_package_phantom_targets(graph: CodeGraph) -> int:
    """Rewrite package::Symbol phantom targets to real node IDs."""
    rewritten = 0
    to_rewrite: list[tuple[str, str, str]] = []

    for u, v, data in graph.iter_edges():
        if data.get("kind") != EdgeKind.CALLS:
            continue
        if graph.get_node(v) is not None:
            continue
        if "::" not in v:
            continue
        qualified = v.split("::", 1)[-1]
        if not qualified:
            continue
        resolved = graph.resolve_symbol(qualified)
        if not resolved or resolved == v:
            continue
        if graph.get_node(resolved) is None:
            continue
        to_rewrite.append((u, v, resolved))

    for u, v, new_target in to_rewrite:
        graph.remove_edge(u, v)
        graph.add_edge(GraphEdge(source=u, target=new_target, kind=EdgeKind.CALLS))
        rewritten += 1

    if rewritten:
        logger.info("Rewrote %d package phantom CALLS targets", rewritten)
    return rewritten


def _prune_phantom_calls(graph: CodeGraph) -> int:
    """Remove CALLS edges to unresolvable phantom targets."""
    to_remove = []
    for u, v, data in graph.iter_edges():
        if data.get("kind") != EdgeKind.CALLS:
            continue
        if graph.get_node(v) is not None:
            continue
        if not graph.has_symbol_candidates(v):
            to_remove.append((u, v))
        elif "::" not in v and "." not in v and graph.has_ambiguous_symbol(v):
            to_remove.append((u, v))

    for u, v in to_remove:
        graph.remove_edge(u, v)

    graph.remove_orphan_phantoms()

    if to_remove:
        logger.info("Pruned %d phantom CALLS edges", len(to_remove))
    return len(to_remove)
