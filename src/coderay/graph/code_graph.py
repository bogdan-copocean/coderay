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
    """Directed graph of code relationships."""

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
            return data.get("data")
        return None

    # ------------------------------------------------------------------
    # Public query methods
    # ------------------------------------------------------------------

    _IMPACT_EDGE_KINDS = frozenset(
        {EdgeKind.CALLS, EdgeKind.IMPORTS, EdgeKind.INHERITS}
    )

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

    def _parent_class_name(self, parent_node_id: str) -> str:
        """Extract class name from parent node ID (last component after ::)."""
        qualifier = (
            parent_node_id.split("::", 1)[-1]
            if "::" in parent_node_id
            else parent_node_id
        )
        return qualifier.split(".")[-1] if "." in qualifier else qualifier

    def get_impact_radius(self, symbol: str, depth: int = 2) -> ImpactResult:
        """Find nodes affected by reverse CALLS/IMPORTS/INHERITS BFS."""
        resolution_warning: str | None = None
        resolved = self.resolve_symbol(symbol)

        if resolved is None:
            resolved, resolution_warning = self._fuzzy_resolve(symbol)

        if resolved is None:
            return self._not_found_result(symbol)

        if resolved not in self._g:
            return self._not_found_result(symbol)

        seeds = self._impact_seeds(resolved)
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        for seed in seeds:
            if seed in self._g:
                for pred in self._g.predecessors(seed):
                    if self._is_impact_edge(pred, seed):
                        queue.append((pred, 1))

        # Also find callers via phantom aliases (bare names, dotted-module
        # forms) for every seed — not just the resolved node.
        for seed in seeds:
            for phantom in self._bare_name_targets(seed):
                if phantom in self._g:
                    for pred in self._g.predecessors(phantom):
                        kinds = self._require_edge_kinds(pred, phantom)
                        if any(kind in self._IMPACT_EDGE_KINDS for kind in kinds):
                            queue.append((pred, 1))

        while queue:
            nid, hop = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            node_data = self.get_node(nid)
            # Module nodes collect all importers as predecessors — expanding
            # them would pull in files unrelated to the queried function.
            if (
                hop < depth
                and nid in self._g
                and (node_data is None or node_data.kind != NodeKind.MODULE)
            ):
                for pred in self._g.predecessors(nid):
                    if pred not in visited and self._is_impact_edge(pred, nid):
                        queue.append((pred, hop + 1))

        resolved_node = self.get_node(resolved)
        own_module = resolved_node.file_path if resolved_node else None
        nodes = [
            self.get_node(nid)
            for nid in visited
            if self.get_node(nid) is not None and nid != own_module
        ]

        # A module node is a strict superset of its function/class nodes;
        # drop it when the file is already represented by a more specific node.
        files_with_non_module = {
            n.file_path for n in nodes if n.kind != NodeKind.MODULE
        }
        nodes = [
            n
            for n in nodes
            if n.kind != NodeKind.MODULE or n.file_path not in files_with_non_module
        ]

        hint = self._zero_callers_hint(resolved) if not nodes else None
        return ImpactResult(
            resolved_node=resolved,
            nodes=nodes,
            hint=hint,
            resolution_warning=resolution_warning,
        )

    def _bare_name_targets(self, node_id: str) -> list[str]:
        """Return phantom nodes that are aliases of the real *node_id*.

        Covers three forms:
        1. Qualified name: ``Class.method`` (already in graph as phantom)
        2. Bare name: ``method`` (unambiguous single candidate)
        3. Dotted-module phantom: ``some.module::Class.method`` — created
           when callers import from a package ``__init__`` and the call
           resolves to the dotted-module form instead of the file path.
        """
        node = self.get_node(node_id)
        if node is None:
            return []
        targets = []
        if node.qualified_name != node_id and node.qualified_name in self._g:
            targets.append(node.qualified_name)
        sym_candidates = self._symbol_index.get(node.name, set())
        if len(sym_candidates) == 1 and node.name in self._g:
            targets.append(node.name)
        # Dotted-module phantoms: "mod.pkg::Class.method" where the symbol
        # part matches this node's qualified_name but the module prefix
        # differs from the file path.  These appear when callers import
        # from a package __init__ that re-exports the symbol.
        qname = node.qualified_name
        suffix = f"::{qname}"
        for candidate in self._g.nodes:
            if candidate == node_id or candidate in targets:
                continue
            if self._g.nodes[candidate].get("data") is not None:
                continue  # real node, not a phantom
            if candidate.endswith(suffix):
                targets.append(candidate)
        return targets

    def _impact_seeds(self, node_id: str) -> list[str]:
        """Return node_id plus same method on parent classes (interface-aware)."""
        seeds = [node_id]
        if "::" not in node_id:
            return seeds
        file_part, qualifier = node_id.split("::", 1)
        if "." not in qualifier:
            return seeds
        class_qualifier, method_name = qualifier.rsplit(".", 1)
        class_node_id = f"{file_part}::{class_qualifier}"
        if class_node_id not in self._g:
            return seeds
        for _, parent in self._g.out_edges(class_node_id):
            edge_kinds = self._require_edge_kinds(class_node_id, parent)
            if EdgeKind.INHERITS not in edge_kinds:
                continue
            parent_method = f"{parent}.{method_name}"
            if parent_method in self._g:
                seeds.append(parent_method)
            else:
                parent_class_name = self._parent_class_name(parent)
                fallback = self.resolve_symbol(f"{parent_class_name}.{method_name}")
                if fallback and fallback not in seeds:
                    seeds.append(fallback)
        return seeds

    def _is_impact_edge(self, source: str, target: str) -> bool:
        """Return True if edge is dependency (not containment)."""
        if not self._g.has_edge(source, target):
            return False
        kinds = self._require_edge_kinds(source, target)
        return any(kind in self._IMPACT_EDGE_KINDS for kind in kinds)

    def _not_found_result(self, symbol: str) -> ImpactResult:
        """Build ImpactResult with hint for missing node."""
        file_part = symbol.split("::")[0] if "::" in symbol else None
        available = sorted(self._file_index.get(file_part, set())) if file_part else []
        hint = f"Node '{symbol}' not in the graph."
        if available:
            hint += f" Available nodes in {file_part}: {available}"
        return ImpactResult(resolved_node=None, nodes=[], hint=hint)

    def _fuzzy_resolve(self, symbol: str) -> tuple[str | None, str | None]:
        """Fuzzy-resolve by method name when exact resolution fails."""
        if "::" not in symbol:
            return None, None

        file_part, qualifier = symbol.split("::", 1)
        file_nodes = self._file_index.get(file_part, set())
        if not file_nodes:
            return None, None

        # Extract the method/function name (last component)
        method_name = qualifier.rsplit(".", 1)[-1] if "." in qualifier else qualifier

        candidates = []
        for nid in file_nodes:
            node = self.get_node(nid)
            if node is None:
                continue
            node_method = node.qualified_name.rsplit(".", 1)[-1]
            if node_method == method_name:
                candidates.append(nid)

        if len(candidates) == 1:
            resolved = candidates[0]
            warning = (
                f"Requested '{qualifier}' not found; "
                f"resolved to '{resolved.split('::', 1)[1]}'"
            )
            return resolved, warning

        return None, None

    def _zero_callers_hint(self, node_id: str) -> str | None:
        """Build hint when node has zero callers."""
        node = self.get_node(node_id)
        if node is None:
            return None

        module_id = node.file_path
        importer_count = 0
        if module_id in self._g:
            for pred in self._g.predecessors(module_id):
                kinds = self._require_edge_kinds(pred, module_id)
                if EdgeKind.IMPORTS in kinds:
                    importer_count += 1

        if importer_count > 0:
            return (
                f"No callers found via static analysis, but this module "
                f"is imported by {importer_count} file(s) — callers may "
                f"exist but couldn't be resolved statically. "
                f"Supplement with grep for the method name."
            )
        return (
            "No callers found. This module is not imported by any other indexed file."
        )

    @property
    def node_count(self) -> int:
        """Return node count (including phantoms)."""
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """Return edge count."""
        return self._g.number_of_edges()

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
            del data  # unused
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
