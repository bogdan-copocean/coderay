from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any

import networkx as nx

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, ImpactResult, NodeKind
from coderay.graph.identifiers import file_path_to_module_names

logger = logging.getLogger(__name__)

GRAPH_SCHEMA_VERSION = 2


class CodeGraph:
    """Directed graph of code relationships.

    Storage and simple lookups live here.
    Impact-radius analysis is delegated to ``ImpactAnalyzer`` (graph/impact.py),
    exposed here for backwards-compatibility via ``get_impact_radius()``.
    """

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()

        # short name -> {full node IDs}
        self._symbol_index: dict[str, set[str]] = defaultdict(set)

        # qualified_name -> {full node IDs}
        self._qualified_index: dict[str, set[str]] = defaultdict(set)

        # dotted module name -> node ID
        self._module_index: dict[str, str] = {}

        # file path -> {node IDs}
        self._file_index: dict[str, set[str]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Node / edge mutation
    # ------------------------------------------------------------------

    def _index_node(self, node: GraphNode) -> None:
        """Register node in all indexes."""
        self._symbol_index[node.name].add(node.id)
        if node.qualified_name != node.name:
            self._qualified_index[node.qualified_name].add(node.id)
        self._file_index[node.file_path].add(node.id)
        if node.kind == NodeKind.MODULE:
            for mod_name in file_path_to_module_names(node.file_path):
                if mod_name not in self._module_index:
                    self._module_index[mod_name] = node.id

    def _unindex_node(self, node: GraphNode) -> None:
        """Remove node from all indexes."""
        sym_entries = self._symbol_index.get(node.name)
        if sym_entries is not None:
            sym_entries.discard(node.id)
        if node.qualified_name != node.name:
            qual_entries = self._qualified_index.get(node.qualified_name)
            if qual_entries is not None:
                qual_entries.discard(node.id)
        file_entries = self._file_index.get(node.file_path)
        if file_entries is not None:
            file_entries.discard(node.id)
        if node.kind == NodeKind.MODULE:
            for mod_name in file_path_to_module_names(node.file_path):
                if self._module_index.get(mod_name) == node.id:
                    del self._module_index[mod_name]

    def add_node(self, node: GraphNode) -> None:
        """Add node and update indexes."""
        self._g.add_node(node.id, data=node)
        self._index_node(node)

    def add_edge(self, edge: GraphEdge) -> None:
        """Add directed edge."""
        if not isinstance(edge.kind, EdgeKind):
            logger.warning(
                "Skipping edge with invalid kind: %s -> %s (%r)",
                edge.source,
                edge.target,
                edge.kind,
            )
            return
        if not self._g.has_edge(edge.source, edge.target):
            self._g.add_edge(edge.source, edge.target, kind={edge.kind})
            return
        kinds = self._require_edge_kinds(edge.source, edge.target)
        kinds.add(edge.kind)

    def add_nodes_and_edges(
        self, nodes: list[GraphNode], edges: list[GraphEdge]
    ) -> None:
        """Add nodes then edges."""
        for n in nodes:
            self.add_node(n)
        for e in edges:
            self.add_edge(e)

    def remove_file(self, file_path: str) -> int:
        """Remove all nodes for file; return count removed."""
        to_remove = self._file_index.pop(file_path, set())
        for nid in to_remove:
            node: GraphNode | None = self._g.nodes[nid].get("data")
            if node:
                self._unindex_node(node)
            self._g.remove_node(nid)
        return len(to_remove)

    def remove_edge(
        self, source: str, target: str, kind: EdgeKind | None = None
    ) -> None:
        """Remove edge, or one kind from a multi-kind edge."""
        if not self._g.has_edge(source, target):
            return
        if kind is None:
            self._g.remove_edge(source, target)
            return
        kinds = self._require_edge_kinds(source, target)
        if kind not in kinds:
            return
        kinds.remove(kind)
        if not kinds:
            self._g.remove_edge(source, target)
            return
        self._g.edges[source, target]["kind"] = kinds

    def edge_has_kind(self, source: str, target: str, kind: EdgeKind) -> bool:
        """Return True if edge has the given kind."""
        if not self._g.has_edge(source, target):
            return False
        kinds = self._require_edge_kinds(source, target)
        return kind in kinds

    def remove_orphan_phantoms(self) -> None:
        """Remove phantom nodes with no edges."""
        orphans = [
            n
            for n in list(self._g.nodes)
            if self._g.nodes[n].get("data") is None and self._g.degree(n) == 0
        ]
        for n in orphans:
            self._g.remove_node(n)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def iter_edges(self):
        """Yield (source, target, data) for each edge."""
        return self._g.edges(data=True)

    def has_symbol_candidates(self, name: str) -> bool:
        """Return True if name has resolution candidates."""
        return bool(self._symbol_index.get(name) or self._qualified_index.get(name))

    def has_ambiguous_symbol(self, name: str) -> bool:
        """Return True if name resolves to multiple candidates."""
        sym = self._symbol_index.get(name, set())
        if len(sym) > 1:
            return True
        qual = self._qualified_index.get(name, set())
        return len(qual) > 1

    def all_file_paths(self) -> set[str]:
        """Return all file paths in graph."""
        return set(self._file_index.keys())

    def resolve_symbol(self, name: str) -> str | None:
        """Resolve name to node ID; None if not unique."""
        if name in self._g and self._g.nodes[name].get("data") is not None:
            return name
        candidates = self._symbol_index.get(name, set())
        if len(candidates) == 1:
            return next(iter(candidates))
        qual_candidates = self._qualified_index.get(name, set())
        if len(qual_candidates) == 1:
            return next(iter(qual_candidates))
        return None

    def get_node(self, node_id: str) -> GraphNode | None:
        """Look up node by ID."""
        data = self._g.nodes.get(node_id)
        if data:
            result: GraphNode | None = data.get("data")
            return result
        return None

    def get_impact_radius(self, symbol: str, depth: int = 2) -> ImpactResult:
        """Find nodes affected by reverse CALLS/IMPORTS/INHERITS BFS."""
        from coderay.graph.impact import ImpactAnalyzer
        return ImpactAnalyzer(self).get_impact_radius(symbol, depth)

    def _require_edge_kinds(self, source: str, target: str) -> set[EdgeKind]:
        """Return edge kinds for a graph edge; enforce internal invariant."""
        raw = self._g.edges[source, target].get("kind")
        if not isinstance(raw, set):
            raise ValueError(f"Edge {source} -> {target} has non-set kinds: {raw!r}")
        if any(not isinstance(kind, EdgeKind) for kind in raw):
            raise ValueError(f"Edge {source} -> {target} has invalid kinds: {raw!r}")
        if not raw:
            raise ValueError(f"Edge {source} -> {target} has empty kinds set")
        return raw

    @property
    def node_count(self) -> int:
        """Return node count (including phantoms)."""
        return int(self._g.number_of_nodes())

    @property
    def edge_count(self) -> int:
        """Return edge count."""
        return int(self._g.number_of_edges())

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to JSON-compatible dict."""
        nodes = []
        for _, data in self._g.nodes(data=True):
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
            del data
            kinds = self._require_edge_kinds(u, v)
            for kind_item in sorted(kinds, key=lambda k: k.value):
                edges_list.append({"source": u, "target": v, "kind": kind_item.value})
        return {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "nodes": nodes,
            "edges": edges_list,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeGraph:
        """Load graph from dict produced by to_dict (schema v1 or v2)."""
        _ = data.get("schema_version", 1)
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
