"""Tests for MCP server tool registration and response format."""

import asyncio
import json
from unittest.mock import MagicMock, patch

from coderay.mcp_server.server import mcp


def _get_tool_names() -> set[str]:
    """Retrieve registered tool names from the FastMCP instance."""
    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
    return {t.name for t in tools}


class TestMCPToolsRegistered:
    """Verify all expected tools are registered on the FastMCP instance."""

    EXPECTED_TOOLS = [
        "semantic_search",
        "get_file_skeleton",
        "get_impact_radius",
        "index_status",
    ]

    REMOVED_TOOLS = [
        "trace_callers",
        "trace_callees",
        "get_dependencies",
        "get_dependents",
        "get_subclasses",
    ]

    def test_all_tools_registered(self):
        tool_names = _get_tool_names()
        for name in self.EXPECTED_TOOLS:
            assert name in tool_names, f"Tool {name!r} not registered"

    def test_removed_tools_not_registered(self):
        tool_names = _get_tool_names()
        for name in self.REMOVED_TOOLS:
            assert name not in tool_names, f"Tool {name!r} should have been removed"


class TestIndexStatus:
    @patch("coderay.mcp_server.server._load_state")
    def test_no_state(self, mock_state):
        from coderay.mcp_server.server import index_status

        mock_state.return_value = None
        result = json.loads(index_status())
        assert result["status"] == "no_index"


class TestGetFileSkeleton:
    def test_missing_file(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        result = json.loads(get_file_skeleton(str(tmp_path / "nope.py")))
        assert "error" in result

    def test_real_file(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        f = tmp_path / "hello.py"
        f.write_text("def greet(): pass")
        result = get_file_skeleton(str(f))
        assert "def greet" in result


class TestSemanticSearch:
    @patch("coderay.mcp_server.server._get_retrieval")
    @patch("coderay.mcp_server.server._load_state")
    def test_no_state(self, mock_state, mock_retrieval):
        from coderay.mcp_server.server import semantic_search

        mock_state.return_value = None
        result = json.loads(semantic_search("hello"))
        assert "error" in result


class TestGetImpactRadius:
    @patch("coderay.mcp_server.server._load_graph")
    def test_no_graph(self, mock_graph):
        from coderay.mcp_server.server import get_impact_radius

        mock_graph.return_value = None
        result = json.loads(get_impact_radius("node"))
        assert "error" in result

    @patch("coderay.mcp_server.server._load_graph")
    def test_response_envelope(self, mock_load):
        from coderay.mcp_server.server import get_impact_radius

        g = MagicMock()
        g.get_impact_radius.return_value = []
        mock_load.return_value = g
        result = json.loads(get_impact_radius("node"))
        assert "results" in result
        assert "note" in result
        assert "static analysis" in result["note"]
