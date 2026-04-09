"""Post-merge: rewrite bare-name phantom CALLS when uniquely resolvable repo-wide."""

from __future__ import annotations

import logging

from coderay.core.models import EdgeKind, GraphEdge
from coderay.graph.code_graph import CodeGraph

logger = logging.getLogger(__name__)


def rewrite_bare_phantom_calls(graph: CodeGraph) -> int:
    """Rewrite bare CALLS targets when ``resolve_symbol`` yields one node id."""
    rewritten = 0
    # Collect (caller, phantom_target, full_node_id); mutate only after the scan.
    to_rewrite: list[tuple[str, str, str]] = []

    for u, v, _ in graph.iter_edges():
        # Only consider CALLS edges (multi-kind pairs may share u→v).
        if not graph.edge_has_kind(u, v, EdgeKind.CALLS):
            continue
        # Target already a real node id — nothing to rewrite.
        if graph.get_node(v) is not None:
            continue
        # Bare name only: skip file-qualified or dotted module-style targets.
        if "::" in v or "." in v:
            continue
        # Multiple repo-wide candidates — do not pick one arbitrarily.
        if graph.has_ambiguous_symbol(v):
            continue
        # Uniquely map short name v to a canonical node id (or None / identity).
        resolved = graph.resolve_symbol(v)
        if not resolved or resolved == v:
            continue
        # Guard: resolver must point at an existing graph node.
        if graph.get_node(resolved) is None:
            continue
        to_rewrite.append((u, v, resolved))

    for u, v, new_target in to_rewrite:
        # Replace phantom string v with full id; keep other edge kinds on u→v intact.
        graph.remove_edge(u, v, kind=EdgeKind.CALLS)
        graph.add_edge(GraphEdge(source=u, target=new_target, kind=EdgeKind.CALLS))
        rewritten += 1

    if rewritten:
        logger.info("Rewrote %d bare phantom CALLS", rewritten)
    return rewritten
