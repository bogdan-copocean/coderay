"""Impact radius analysis: reverse BFS over the code graph."""

from __future__ import annotations

from collections import deque

from coderay.core.models import EdgeKind, GraphNode, ImpactResult, NodeKind

_IMPACT_EDGE_KINDS = frozenset({EdgeKind.CALLS, EdgeKind.IMPORTS, EdgeKind.INHERITS})


class ImpactAnalyzer:
    """Domain queries on top of a CodeGraph store.

    Owns: phantom aliasing, inheritance seed expansion, fuzzy resolution,
    zero-callers hints.  The graph store is injected and used read-only.
    """

    def __init__(self, graph) -> None:
        # Accepts CodeGraph; typed as Any to avoid circular import at the type level.
        self._graph = graph

    def get_impact_radius(self, symbol: str, depth: int = 2) -> ImpactResult:
        """Find nodes affected by a change to *symbol* (reverse BFS)."""
        g = self._graph
        resolution_warning: str | None = None
        resolved = g.resolve_symbol(symbol)

        if resolved is None:
            resolved, resolution_warning = self._fuzzy_resolve(symbol)

        if resolved is None:
            return self._ambiguous_or_not_found(symbol)

        if resolved not in g._g:
            return self._not_found(symbol)

        seeds = self._impact_seeds(resolved)
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        for seed in seeds:
            if seed in g._g:
                for pred in g._g.predecessors(seed):
                    if self._is_impact_edge(pred, seed):
                        queue.append((pred, 1))

        for seed in seeds:
            for phantom in self._bare_name_targets(seed):
                if phantom in g._g:
                    for pred in g._g.predecessors(phantom):
                        kinds = g._require_edge_kinds(pred, phantom)
                        if any(kind in _IMPACT_EDGE_KINDS for kind in kinds):
                            queue.append((pred, 1))

        while queue:
            nid, hop = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            node_data = g.get_node(nid)
            if (
                hop < depth
                and nid in g._g
                and (node_data is None or node_data.kind != NodeKind.MODULE)
            ):
                for pred in g._g.predecessors(nid):
                    if pred not in visited and self._is_impact_edge(pred, nid):
                        queue.append((pred, hop + 1))

        resolved_node = g.get_node(resolved)
        own_module = resolved_node.file_path if resolved_node else None
        raw_nodes: list[GraphNode] = [
            n
            for nid in visited
            if (n := g.get_node(nid)) is not None and nid != own_module
        ]
        files_with_non_module = {
            n.file_path for n in raw_nodes if n.kind != NodeKind.MODULE
        }
        filtered: list[GraphNode] = [
            n
            for n in raw_nodes
            if n.kind != NodeKind.MODULE or n.file_path not in files_with_non_module
        ]
        hint = self._zero_callers_hint(resolved) if not filtered else None
        return ImpactResult(
            resolved_node=resolved,
            nodes=filtered,
            hint=hint,
            resolution_warning=resolution_warning,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _bare_name_targets(self, node_id: str) -> list[str]:
        g = self._graph
        node = g.get_node(node_id)
        if node is None:
            return []
        targets = []
        if node.qualified_name != node_id and node.qualified_name in g._g:
            targets.append(node.qualified_name)
        sym_candidates = g._symbol_index.get(node.name, set())
        if len(sym_candidates) == 1 and node.name in g._g:
            targets.append(node.name)
        qname = node.qualified_name
        suffix = f"::{qname}"
        for candidate in g._g.nodes:
            if candidate == node_id or candidate in targets:
                continue
            if g._g.nodes[candidate].get("data") is not None:
                continue
            if candidate.endswith(suffix):
                targets.append(candidate)
        return targets

    def _impact_seeds(self, node_id: str) -> list[str]:
        g = self._graph
        seeds = [node_id]
        if "::" not in node_id:
            return seeds
        file_part, qualifier = node_id.split("::", 1)
        if "." not in qualifier:
            return seeds
        class_qualifier, method_name = qualifier.rsplit(".", 1)
        class_node_id = f"{file_part}::{class_qualifier}"
        if class_node_id not in g._g:
            return seeds
        for _, parent in g._g.out_edges(class_node_id):
            edge_kinds = g._require_edge_kinds(class_node_id, parent)
            if EdgeKind.INHERITS not in edge_kinds:
                continue
            parent_method = f"{parent}.{method_name}"
            if parent_method in g._g:
                seeds.append(parent_method)
            else:
                parent_class_name = _last_component(parent)
                fallback = g.resolve_symbol(f"{parent_class_name}.{method_name}")
                if fallback and fallback not in seeds:
                    seeds.append(fallback)
        return seeds

    def _is_impact_edge(self, source: str, target: str) -> bool:
        g = self._graph
        if not g._g.has_edge(source, target):
            return False
        kinds = g._require_edge_kinds(source, target)
        return any(kind in _IMPACT_EDGE_KINDS for kind in kinds)

    def _not_found(self, symbol: str) -> ImpactResult:
        g = self._graph
        file_part = symbol.split("::")[0] if "::" in symbol else None
        available = sorted(g._file_index.get(file_part, set())) if file_part else []
        hint = f"Node '{symbol}' not in the graph."
        if available:
            hint += f" Available nodes in {file_part}: {available}"
        return ImpactResult(resolved_node=None, nodes=[], hint=hint)

    def _ambiguous_or_not_found(self, symbol: str) -> ImpactResult:
        g = self._graph
        sym_candidates = g._symbol_index.get(symbol, set())
        qual_candidates = g._qualified_index.get(symbol, set())
        all_candidates = sym_candidates | qual_candidates
        if len(all_candidates) > 1:
            listed = "\n".join(f"  {c}" for c in sorted(all_candidates))
            hint = (
                f"Symbol '{symbol}' is ambiguous. Candidates:\n{listed}\n"
                f"Specify one of these as the node ID."
            )
            return ImpactResult(resolved_node=None, nodes=[], hint=hint)
        return self._not_found(symbol)

    def _fuzzy_resolve(self, symbol: str) -> tuple[str | None, str | None]:
        g = self._graph
        if "::" not in symbol:
            return None, None
        file_part, qualifier = symbol.split("::", 1)
        file_nodes = g._file_index.get(file_part, set())
        if not file_nodes:
            return None, None
        method_name = qualifier.rsplit(".", 1)[-1] if "." in qualifier else qualifier
        candidates = [
            nid
            for nid in file_nodes
            if (node := g.get_node(nid)) is not None
            and node.qualified_name.rsplit(".", 1)[-1] == method_name
        ]
        if len(candidates) == 1:
            resolved = candidates[0]
            warning = (
                f"Requested '{qualifier}' not found; "
                f"resolved to '{resolved.split('::', 1)[1]}'"
            )
            return resolved, warning
        return None, None

    def _zero_callers_hint(self, node_id: str) -> str | None:
        g = self._graph
        node = g.get_node(node_id)
        if node is None:
            return None
        module_id = node.file_path
        importer_count = (
            sum(
                1
                for pred in g._g.predecessors(module_id)
                if EdgeKind.IMPORTS in g._require_edge_kinds(pred, module_id)
            )
            if module_id in g._g
            else 0
        )
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


def _last_component(node_id: str) -> str:
    """Extract the last dotted component after :: (class name)."""
    qualifier = node_id.split("::", 1)[-1] if "::" in node_id else node_id
    return qualifier.split(".")[-1] if "." in qualifier else qualifier
