"""Tests for indexer.core.models."""

import pytest

from coderay.core.models import GraphNode, ImpactResult, NodeKind


class TestImpactResult:
    def _node(self) -> GraphNode:
        return GraphNode(
            id="a.py::foo",
            kind=NodeKind.FUNCTION,
            file_path="a.py",
            start_line=1,
            end_line=5,
            name="foo",
            qualified_name="foo",
        )

    @pytest.mark.parametrize(
        "resolved_node,nodes,hint,expected_resolved,expected_results,has_hint",
        [
            ("a.py::foo", "one", None, "a.py::foo", 1, False),
            (None, "none", "Node not found.", None, 0, True),
            ("x", "none", None, "x", 0, False),
        ],
    )
    def test_to_dict_roundtrip(
        self, resolved_node, nodes, hint, expected_resolved, expected_results, has_hint
    ):
        nodes_list = [self._node()] if nodes == "one" else []
        r = ImpactResult(resolved_node=resolved_node, nodes=nodes_list, hint=hint)
        d = r.to_dict()
        assert d["resolved_node"] == expected_resolved
        assert len(d["results"]) == expected_results
        assert ("hint" in d) == has_hint
