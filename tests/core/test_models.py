"""Tests for indexer.core.models."""

import pytest

from coderay.core.models import (
    Chunk,
    EdgeKind,
    GraphEdge,
    GraphNode,
    ImpactResult,
    NodeKind,
)


class TestChunk:
    def test_line_range(self):
        c = Chunk(
            path="a.py",
            start_line=3,
            end_line=7,
            symbol="f",
            content="",
        )
        assert c.line_range() == (3, 7)


class TestGraphNode:
    def test_frozen(self):
        n = GraphNode(
            id="x",
            kind=NodeKind.MODULE,
            file_path="a.py",
            start_line=1,
            end_line=10,
            name="a",
            qualified_name="a",
        )
        with pytest.raises(AttributeError):
            n.id = "y"


class TestGraphEdge:
    def test_frozen(self):
        e = GraphEdge(source="a", target="b", kind=EdgeKind.CALLS)
        with pytest.raises(AttributeError):
            e.source = "c"


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

    def test_to_dict_with_results(self):
        n = self._node()
        r = ImpactResult(resolved_node="a.py::foo", nodes=[n])
        d = r.to_dict()
        assert d["resolved_node"] == "a.py::foo"
        assert len(d["results"]) == 1
        assert "hint" not in d

    def test_to_dict_with_hint(self):
        r = ImpactResult(resolved_node=None, nodes=[], hint="Node not found.")
        d = r.to_dict()
        assert d["resolved_node"] is None
        assert d["results"] == []
        assert d["hint"] == "Node not found."

    def test_to_dict_no_hint_when_none(self):
        r = ImpactResult(resolved_node="x", nodes=[])
        d = r.to_dict()
        assert "hint" not in d

    def test_frozen(self):
        r = ImpactResult(resolved_node="x", nodes=[])
        with pytest.raises(AttributeError):
            r.resolved_node = "y"  # type: ignore[misc]
