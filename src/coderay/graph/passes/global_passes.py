"""Language-agnostic passes after merge."""

from __future__ import annotations

from coderay.graph.code_graph import CodeGraph


def run_global_passes(graph: CodeGraph) -> None:
    """Hook for dedupe, orphan cleanup, etc."""
    _ = graph
