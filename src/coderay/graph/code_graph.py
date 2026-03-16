from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import networkx as nx

from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.parsing.languages import (
    get_init_filenames,
    get_resolution_suffixes,
    get_supported_extensions,
)

logger = logging.getLogger(__name__)


_KNOWN_EXTENSIONS: frozenset[str] = frozenset()
_KNOWN_INIT_FILENAMES: frozenset[str] = frozenset()


def _ensure_registry_cache() -> None:
    """Lazily populate the cached extension and init filename sets."""
    global _KNOWN_EXTENSIONS, _KNOWN_INIT_FILENAMES  # noqa: PLW0603
    if not _KNOWN_EXTENSIONS:
        _KNOWN_EXTENSIONS = frozenset(get_supported_extensions())
        _KNOWN_INIT_FILENAMES = frozenset(get_init_filenames())


def _file_path_to_module_names(file_path: str) -> list[str]:
    """Derive possible module names from a file path."""
    _ensure_registry_cache()

    # Strip file extension using the registry
    cleaned = file_path
    for ext in sorted(_KNOWN_EXTENSIONS, key=len, reverse=True):
        if cleaned.endswith(ext):
            cleaned = cleaned[: -len(ext)]
            break

    parts = cleaned.replace("\\", "/").split("/")

    # Strip common layout prefixes
    if parts and parts[0] == "src":
        parts = parts[1:]

    # Strip init-style filenames (Python __init__, JS/TS index)
    if parts and parts[-1] in _KNOWN_INIT_FILENAMES:
        parts = parts[:-1]

    if not parts:
        return []

    names: list[str] = []
    for i in range(len(parts)):
        suffix = parts[i:]
        dotted = ".".join(suffix)
        names.append(dotted)
        slashed = "/".join(suffix)
        if slashed != dotted:
            names.append(slashed)
    return names


class CodeGraph:
    """In-memory directed graph of code relationships."""

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()

        # short name -> {full node IDs} — enables resolving bare names like
        # "foo" to "src/utils.py::foo". Multiple IDs when the name is ambiguous
        # (e.g. two files both define a function called "helper").
        self._symbol_index: dict[str, set[str]] = defaultdict(set)

        # qualified_name -> {full node IDs} — enables resolving dotted names
        # like "ClassName.method" to "src/a.py::ClassName.method".
        self._qualified_index: dict[str, set[str]] = defaultdict(set)

        # dotted module name -> node ID — maps Python-style import paths
        # (e.g. "core.models") to the MODULE node they refer to.
        self._module_index: dict[str, str] = {}

        # file path -> {node IDs} — all nodes belonging to a file, for O(k)
        # file removal instead of scanning the entire graph.
        self._file_index: dict[str, set[str]] = defaultdict(set)

    def _index_node(self, node: GraphNode) -> None:
        """Register a node in all secondary indexes."""
        self._symbol_index[node.name].add(node.id)
        if node.qualified_name != node.name:
            self._qualified_index[node.qualified_name].add(node.id)
        self._file_index[node.file_path].add(node.id)
        if node.kind == NodeKind.MODULE:
            # Register all suffix variants so that "import models" and
            # "import core.models" both resolve to the same MODULE node.
            for mod_name in _file_path_to_module_names(node.file_path):
                if mod_name not in self._module_index:
                    self._module_index[mod_name] = node.id

    def _unindex_node(self, node: GraphNode) -> None:
        """Remove a node from all secondary indexes."""
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
            for mod_name in _file_path_to_module_names(node.file_path):
                if self._module_index.get(mod_name) == node.id:
                    del self._module_index[mod_name]

    def add_node(self, node: GraphNode) -> None:
        """Insert a node into the graph and update all secondary indexes."""
        self._g.add_node(node.id, data=node)
        self._index_node(node)

    def add_edge(self, edge: GraphEdge) -> None:
        """Insert a directed edge."""
        self._g.add_edge(edge.source, edge.target, kind=edge.kind)

    def add_nodes_and_edges(
        self, nodes: list[GraphNode], edges: list[GraphEdge]
    ) -> None:
        """Bulk-insert nodes then edges (order matters — nodes first)."""
        for n in nodes:
            self.add_node(n)
        for e in edges:
            self.add_edge(e)

    def remove_file(self, file_path: str) -> int:
        """Remove all nodes belonging to a file and clean up every index.

        Returns:
            Number of nodes removed.
        """
        to_remove = self._file_index.pop(file_path, set())
        for nid in to_remove:
            node: GraphNode | None = self._g.nodes[nid].get("data")
            if node:
                self._unindex_node(node)
            # NetworkX also removes all edges touching this node
            self._g.remove_node(nid)
        return len(to_remove)

    def resolve_symbol(self, name: str, caller_file: str | None = None) -> str | None:
        """Resolve a short, qualified, or dotted name to a fully-qualified node ID.

        Lookup order:
            1. Exact node ID match (fast path).
            2. Bare name via ``_symbol_index`` (unique match only).
            3. Qualified name via ``_qualified_index`` (e.g. "ClassName.method").

        Returns:
            Full node ID, or None if the name cannot be uniquely resolved.
        """
        if name in self._g and self._g.nodes[name].get("data") is not None:
            return name

        candidates = self._symbol_index.get(name, set())
        if len(candidates) == 1:
            return next(iter(candidates))

        qual_candidates = self._qualified_index.get(name, set())
        if len(qual_candidates) == 1:
            return next(iter(qual_candidates))

        return None

    def resolve_edges(self) -> int:
        """Rewire phantom edge targets to real node IDs.

        Returns:
            Number of edges successfully resolved.
        """
        resolvable = {EdgeKind.CALLS, EdgeKind.INHERITS, EdgeKind.IMPORTS}
        to_remove: list[tuple[str, str]] = []
        to_add: list[tuple[str, str, dict]] = []

        for u, v, data in self._g.edges(data=True):
            kind = data.get("kind")
            if kind not in resolvable:
                continue
            # Target is already a real node — nothing to resolve
            if v in self._g and self._g.nodes[v].get("data") is not None:
                continue

            # Extract the caller's file path from its node ID
            # ("src/a.py::MyClass.method" -> "src/a.py")
            caller_file = u.split("::")[0] if "::" in u else u
            resolved = self.resolve_symbol(v, caller_file=caller_file)
            if not resolved and kind == EdgeKind.IMPORTS:
                resolved = self._module_index.get(v)
            if not resolved and kind == EdgeKind.IMPORTS:
                resolved = self._resolve_path_target(v)
            if resolved and resolved != v:
                to_remove.append((u, v))
                to_add.append((u, resolved, dict(data)))

        # Apply changes in a second pass (safe to mutate now)
        for u, v in to_remove:
            if self._g.has_edge(u, v):
                self._g.remove_edge(u, v)
        for u, v, data in to_add:
            self._g.add_edge(u, v, **data)

        if to_add:
            logger.info("Resolved %d edges via symbol/module index", len(to_add))
        return len(to_add)

    def prune_phantom_edges(self) -> int:
        """Remove CALLS edges whose target is a phantom with no resolution candidates.

        These are typically stdlib/third-party methods (``append``, ``get``,
        ``join``, etc.) that will never resolve to a project node.  Removing
        them reduces noise and improves ``get_impact_radius`` traversal.

        Returns:
            Number of edges pruned.
        """
        to_remove: list[tuple[str, str]] = []
        for u, v, data in self._g.edges(data=True):
            if data.get("kind") != EdgeKind.CALLS:
                continue
            node_data = self._g.nodes.get(v, {})
            if node_data and node_data.get("data") is not None:
                continue
            if (
                not self._symbol_index.get(v)
                and not self._qualified_index.get(v)
            ):
                to_remove.append((u, v))

        for u, v in to_remove:
            if self._g.has_edge(u, v):
                self._g.remove_edge(u, v)

        # Clean up orphan phantom nodes (no remaining edges)
        phantom_nodes = [
            n for n in list(self._g.nodes)
            if self._g.nodes[n].get("data") is None
            and self._g.degree(n) == 0
        ]
        for n in phantom_nodes:
            self._g.remove_node(n)

        if to_remove:
            logger.info("Pruned %d phantom CALLS edges", len(to_remove))
        return len(to_remove)

    def _resolve_path_target(self, target: str) -> str | None:
        """Try to match a path-style target to an existing MODULE node."""
        if "/" not in target:
            return None
        for suffix in get_resolution_suffixes():
            candidate = target + suffix
            node_data = self._g.nodes.get(candidate, {})
            if node_data and node_data.get("data") is not None:
                return candidate
        cleaned = target
        if cleaned.startswith("src/"):
            cleaned = cleaned[4:]
        dotted = cleaned.replace("/", ".")
        return self._module_index.get(dotted)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Look up a node by its full ID. Returns None for phantoms or missing nodes."""
        data = self._g.nodes.get(node_id)
        if data:
            return data.get("data")
        return None

    # ------------------------------------------------------------------
    # Public query methods
    # ------------------------------------------------------------------

    def get_impact_radius(self, symbol: str, depth: int = 2) -> list[GraphNode]:
        """Find all nodes that could be affected if ``symbol`` changes.

        Args:
            depth: Number of reverse-BFS hops. Higher values may return
                very large sets.
        """
        resolved = self.resolve_symbol(symbol) or symbol
        if resolved not in self._g:
            return []
        visited: set[str] = set()
        frontier = {resolved}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                if nid not in self._g:
                    continue
                for pred in self._g.predecessors(nid):
                    if pred not in visited:
                        visited.add(pred)
                        next_frontier.add(pred)
            frontier = next_frontier
        return [self.get_node(nid) for nid in visited if self.get_node(nid) is not None]

    @property
    def node_count(self) -> int:
        """Total nodes in the graph (including phantoms)."""
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """Total edges in the graph."""
        return self._g.number_of_edges()

    # ------------------------------------------------------------------
    # Serialisation
    #
    # The graph is persisted as JSON (graph.json). Only real nodes are
    # serialised — phantom nodes are recreated implicitly when edges
    # referencing them are re-added. Secondary indexes are rebuilt by
    # ``add_node`` during ``from_dict``.
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the graph to a JSON-compatible dict."""
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
        """Deserialise a graph from a dict produced by ``to_dict``."""
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
