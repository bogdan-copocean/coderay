"""Tests for MCP server tool registration and response format."""

import json
from unittest.mock import MagicMock, patch

import pytest

from indexer.mcp.server import mcp


class TestMCPToolsRegistered:
    """Verify all expected tools are registered on the FastMCP instance."""

    EXPECTED_TOOLS = [
        "semantic_search",
        "get_file_skeleton",
        "trace_callers",
        "trace_callees",
        "get_dependencies",
        "get_dependents",
        "get_subclasses",
        "get_impact_radius",
        "index_status",
    ]

    def test_all_tools_registered(self):
        tool_names = set()
        for tool in mcp._tool_manager._tools.values():
            tool_names.add(tool.name)
        for name in self.EXPECTED_TOOLS:
            assert name in tool_names, f"Tool {name!r} not registered"


class TestIndexStatus:
    @patch("indexer.mcp.server._load_state")
    def test_no_state(self, mock_state):
        from indexer.mcp.server import index_status

        mock_state.return_value = None
        result = json.loads(index_status())
        assert result["status"] == "no_index"


class TestGetFileSkeleton:
    def test_missing_file(self, tmp_path):
        from indexer.mcp.server import get_file_skeleton

        result = json.loads(get_file_skeleton(str(tmp_path / "nope.py")))
        assert "error" in result

    def test_real_file(self, tmp_path):
        from indexer.mcp.server import get_file_skeleton

        f = tmp_path / "hello.py"
        f.write_text("def greet(): pass")
        result = get_file_skeleton(str(f))
        assert "def greet" in result


class TestSemanticSearch:
    @patch("indexer.mcp.server._get_retrieval")
    @patch("indexer.mcp.server._load_state")
    def test_no_state(self, mock_state, mock_retrieval):
        from indexer.mcp.server import semantic_search

        mock_state.return_value = None
        result = json.loads(semantic_search("hello"))
        assert "error" in result


class TestGraphTools:
    @patch("indexer.mcp.server._load_graph")
    def test_trace_callers_no_graph(self, mock_graph):
        from indexer.mcp.server import trace_callers

        mock_graph.return_value = None
        result = json.loads(trace_callers("foo"))
        assert "error" in result

    @patch("indexer.mcp.server._load_graph")
    def test_trace_callees_no_graph(self, mock_graph):
        from indexer.mcp.server import trace_callees

        mock_graph.return_value = None
        result = json.loads(trace_callees("foo"))
        assert "error" in result

    @patch("indexer.mcp.server._load_graph")
    def test_get_dependencies_no_graph(self, mock_graph):
        from indexer.mcp.server import get_dependencies

        mock_graph.return_value = None
        result = json.loads(get_dependencies("mod.py"))
        assert "error" in result

    @patch("indexer.mcp.server._load_graph")
    def test_get_dependents_no_graph(self, mock_graph):
        from indexer.mcp.server import get_dependents

        mock_graph.return_value = None
        result = json.loads(get_dependents("mod.py"))
        assert "error" in result

    @patch("indexer.mcp.server._load_graph")
    def test_get_subclasses_no_graph(self, mock_graph):
        from indexer.mcp.server import get_subclasses

        mock_graph.return_value = None
        result = json.loads(get_subclasses("MyClass"))
        assert "error" in result

    @patch("indexer.mcp.server._load_graph")
    def test_get_impact_radius_no_graph(self, mock_graph):
        from indexer.mcp.server import get_impact_radius

        mock_graph.return_value = None
        result = json.loads(get_impact_radius("node"))
        assert "error" in result
