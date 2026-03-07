"""CodeGraph: in-memory directed graph with LLM-friendly query API.

Wraps a NetworkX DiGraph. Nodes carry GraphNode metadata; edges carry EdgeKind.
All query methods return lists of GraphNode for easy serialisation to MCP
responses / JSON.

A symbol index (short name -> list of node IDs) enables O(1) lookup and
best-effort resolution of unqualified call targets.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import networkx as nx

from indexer.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind

logger = logging.getLogger(__name__)


class CodeGraph:
    """Query interface over a code-relationship graph."""

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()
        self._symbol_index: dict[str, list[str]] = defaultdict(list)

    def _index_node(self, node: GraphNode) -> None:
        """Add a node's short name to the symbol index."""
        self._symbol_index[node.name].append(node.id)

    def add_node(self, node: GraphNode) -> None:
        self._g.add_node(node.id, data=node)
        self._index_node(node)

    def add_edge(self, edge: GraphEdge) -> None:
        self._g.add_edge(edge.source, edge.target, kind=edge.kind)

    def add_nodes_and_edges(
        self, nodes: list[GraphNode], edges: list[GraphEdge]
    ) -> None:
        for n in nodes:
            self.add_node(n)
        for e in edges:
            self.add_edge(e)

    def remove_file(self, file_path: str) -> int:
        """Remove all nodes (and their edges) belonging to a file.

        Returns the number of nodes removed.
        """
        to_remove = [
            nid
            for nid, data in self._g.nodes(data=True)
            if data.get("data") is not None and data["data"].file_path == file_path
        ]
        for nid in to_remove:
            node: GraphNode | None = self._g.nodes[nid].get("data")
            if node:
                entries = self._symbol_index.get(node.name, [])
                if nid in entries:
                    entries.remove(nid)
            self._g.remove_node(nid)
        return len(to_remove)

    def resolve_symbol(self, name: str) -> str | None:
        """Resolve a short name to a unique node ID, or None if ambiguous.

        Only considers nodes that were explicitly added (have metadata),
        not phantom nodes auto-created by NetworkX from edge endpoints.
        """
        if name in self._g and self._g.nodes[name].get("data") is not None:
            return name
        candidates = self._symbol_index.get(name, [])
        if len(candidates) == 1:
            return candidates[0]
        return None

    def resolve_edges(self) -> int:
        """Resolve CALLS edges whose targets are unresolved short names.

        For each CALLS edge where the target node doesn't exist in the graph,
        attempt to resolve via the symbol index. If exactly one match,
        rewire the edge. Returns the number of edges resolved.
        """
        to_remove: list[tuple[str, str]] = []
        to_add: list[tuple[str, str, dict]] = []

        for u, v, data in self._g.edges(data=True):
            if data.get("kind") != EdgeKind.CALLS:
                continue
            if v in self._g and self._g.nodes[v].get("data") is not None:
                continue
            resolved = self.resolve_symbol(v)
            if resolved and resolved != v:
                to_remove.append((u, v))
                to_add.append((u, resolved, dict(data)))

        for u, v in to_remove:
            self._g.remove_edge(u, v)
        for u, v, data in to_add:
            self._g.add_edge(u, v, **data)

        if to_add:
            logger.info("Resolved %d call edges via symbol index", len(to_add))
        return len(to_add)

    def get_node(self, node_id: str) -> GraphNode | None:
        data = self._g.nodes.get(node_id)
        if data:
            return data.get("data")
        return None

    def get_dependencies(self, module: str) -> list[GraphNode]:
        return self._neighbours_by_edge(module, EdgeKind.IMPORTS, direction="out")

    def get_dependents(self, module: str) -> list[GraphNode]:
        return self._neighbours_by_edge(module, EdgeKind.IMPORTS, direction="in")

    def get_callers(self, function: str) -> list[GraphNode]:
        return self._neighbours_by_edge(function, EdgeKind.CALLS, direction="in")

    def get_callees(self, function: str) -> list[GraphNode]:
        return self._neighbours_by_edge(function, EdgeKind.CALLS, direction="out")

    def get_subclasses(self, class_name: str) -> list[GraphNode]:
        return self._neighbours_by_edge(class_name, EdgeKind.INHERITS, direction="in")

    def get_definitions(self, module: str) -> list[GraphNode]:
        return self._neighbours_by_edge(module, EdgeKind.DEFINES, direction="out")

    def get_impact_radius(self, symbol: str, depth: int = 2) -> list[GraphNode]:
        resolved = self.resolve_symbol(symbol) or symbol
        visited: set[str] = set()
        frontier = {resolved}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                for pred in self._g.predecessors(nid):
                    if pred not in visited:
                        visited.add(pred)
                        next_frontier.add(pred)
            frontier = next_frontier
        return [self.get_node(nid) for nid in visited if self.get_node(nid) is not None]

    def shortest_path(self, from_sym: str, to_sym: str) -> list[GraphNode]:
        src = self.resolve_symbol(from_sym) or from_sym
        dst = self.resolve_symbol(to_sym) or to_sym
        try:
            path_ids = nx.shortest_path(self._g.to_undirected(), src, dst)
            return [
                self.get_node(nid) for nid in path_ids if self.get_node(nid) is not None
            ]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    @property
    def node_count(self) -> int:
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._g.number_of_edges()

    def to_dict(self) -> dict[str, Any]:
        nodes = []
        for nid, data in self._g.nodes(data=True):
            gn: GraphNode | None = data.get("data") if data else None
            if gn:
                nodes.append(
                    {
                        "id": gn.id,
                        "kind": gn.kind.value,
                        "file_path": gn.file_path,
                        "start_line": gn.start_line,
                        "end_line": gn.end_line,
                        "name": gn.name,
                        "qualified_name": gn.qualified_name,
                    }
                )
        edges_list = []
        for u, v, data in self._g.edges(data=True):
            kind = data.get("kind", "")
            kind_val = kind.value if hasattr(kind, "value") else str(kind)
            edges_list.append({"source": u, "target": v, "kind": kind_val})
        return {"nodes": nodes, "edges": edges_list}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeGraph:
        graph = cls()
        for nd in data.get("nodes", []):
            graph.add_node(
                GraphNode(
                    id=nd["id"],
                    kind=NodeKind(nd["kind"]),
                    file_path=nd["file_path"],
                    start_line=nd["start_line"],
                    end_line=nd["end_line"],
                    name=nd["name"],
                    qualified_name=nd["qualified_name"],
                )
            )
        for ed in data.get("edges", []):
            graph.add_edge(
                GraphEdge(
                    source=ed["source"],
                    target=ed["target"],
                    kind=EdgeKind(ed["kind"]),
                )
            )
        return graph

    def _neighbours_by_edge(
        self, node_id: str, kind: EdgeKind, direction: str
    ) -> list[GraphNode]:
        resolved = self.resolve_symbol(node_id)
        if resolved:
            node_id = resolved
        elif node_id not in self._g:
            return []

        if direction == "out":
            candidates = list(self._g.successors(node_id))
        else:
            candidates = list(self._g.predecessors(node_id))
        results: list[GraphNode] = []
        for cid in candidates:
            if direction == "out":
                edge_data = self._g.edges[node_id, cid]
            else:
                edge_data = self._g.edges[cid, node_id]
            if edge_data.get("kind") == kind:
                gn = self.get_node(cid)
                results.append(gn or GraphNode.external(cid))
        return results
