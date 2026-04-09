"""Tests for fact materialisation and external-edge filtering."""

from __future__ import annotations

from coderay.core.models import EdgeKind, GraphEdge, NodeKind
from coderay.graph.facts import ModuleInfo, SymbolDefinition
from coderay.graph.lowering.cst_helpers import node_id
from coderay.graph.materialise import filter_external_edges, materialise_graph


class TestMaterialiseGraph:
    """materialise_graph invariants."""

    def test_defines_chain_matches_node_id(self) -> None:
        """DEFINES edges use definer_id -> symbol id per node_id()."""
        fp = "pkg/mod.py"
        mod_id = fp
        facts = [
            ModuleInfo(file_path=fp, end_line=100),
            SymbolDefinition(
                file_path=fp,
                scope_stack=(),
                name="C",
                kind=NodeKind.CLASS,
                start_line=2,
                end_line=10,
                definer_id=mod_id,
            ),
            SymbolDefinition(
                file_path=fp,
                scope_stack=("C",),
                name="m",
                kind=NodeKind.FUNCTION,
                start_line=4,
                end_line=8,
                definer_id=node_id(fp, ["C"]),
            ),
        ]
        nodes, edges = materialise_graph(facts)
        class_id = node_id(fp, [], "C")
        method_id = node_id(fp, ["C"], "m")
        defines = {(e.source, e.target) for e in edges if e.kind == EdgeKind.DEFINES}
        assert defines == {(mod_id, class_id), (class_id, method_id)}
        ids = {n.id for n in nodes}
        assert mod_id in ids and class_id in ids and method_id in ids


class TestFilterExternalEdges:
    """filter_external_edges."""

    def test_keeps_internal_file_qualified(self) -> None:
        """Drop targets that are not repo files or file:: prefixes."""
        known = {"in.py"}
        edges = [
            GraphEdge(source="in.py", target="in.py::f", kind=EdgeKind.CALLS),
            GraphEdge(source="in.py", target="ext.pkg.fn", kind=EdgeKind.CALLS),
            GraphEdge(source="in.py", target="bare", kind=EdgeKind.CALLS),
        ]
        out = filter_external_edges(edges, known)
        assert len(out) == 1
        assert out[0].target == "in.py::f"
