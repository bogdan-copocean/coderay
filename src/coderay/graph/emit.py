"""Emit GraphNode/GraphEdge from extracted facts."""

from __future__ import annotations

from collections.abc import Iterable

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.graph.facts import (
    CallsEdge,
    Fact,
    ImportsEdge,
    InheritsEdge,
    ModuleInfo,
    SymbolDefinition,
)


def emit_graph(facts: Iterable[Fact]) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Turn fact stream into graph primitives."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for f in facts:
        if isinstance(f, ModuleInfo):
            nodes.append(
                GraphNode(
                    id=f.file_path,
                    kind=NodeKind.MODULE,
                    file_path=f.file_path,
                    start_line=1,
                    end_line=f.end_line,
                    name=f.file_path,
                    qualified_name=f.file_path,
                )
            )
        elif isinstance(f, SymbolDefinition):
            qualified = ".".join([*f.scope_stack, f.name])
            node_id = f"{f.file_path}::{qualified}"
            nodes.append(
                GraphNode(
                    id=node_id,
                    kind=f.kind,
                    file_path=f.file_path,
                    start_line=f.start_line,
                    end_line=f.end_line,
                    name=f.name,
                    qualified_name=qualified,
                )
            )
            edges.append(
                GraphEdge(source=f.definer_id, target=node_id, kind=EdgeKind.DEFINES)
            )
        elif isinstance(f, ImportsEdge):
            edges.append(
                GraphEdge(source=f.source_id, target=f.target, kind=EdgeKind.IMPORTS)
            )
        elif isinstance(f, CallsEdge):
            edges.append(
                GraphEdge(source=f.source_id, target=f.target, kind=EdgeKind.CALLS)
            )
        elif isinstance(f, InheritsEdge):
            edges.append(
                GraphEdge(source=f.source_id, target=f.target, kind=EdgeKind.INHERITS)
            )
    return nodes, edges


def _is_internal_target(target: str, known_files: set[str]) -> bool:
    """Return True if target's file-path prefix is a known repo file."""
    if target in known_files:
        return True
    if "::" in target:
        return target.split("::", 1)[0] in known_files
    return False


def filter_external_edges(
    edges: list[GraphEdge], known_files: set[str]
) -> list[GraphEdge]:
    """Keep only edges whose target belongs to a repo file."""
    return [e for e in edges if _is_internal_target(e.target, known_files)]
