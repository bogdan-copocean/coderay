"""Tests for MCP server tool/resource registration and response format."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from coderay.core.models import ImpactResult
from coderay.mcp_server.errors import IndexNotBuiltError
from coderay.mcp_server.server import mcp


def _get_tool_names() -> set[str]:
    """Return registered tool names."""
    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
    return {t.name for t in tools}


def _get_resource_uris() -> set[str]:
    """Return registered resource URIs."""
    resources = asyncio.get_event_loop().run_until_complete(mcp.list_resources())
    return {str(r.uri) for r in resources}


class TestMCPToolsRegistered:
    """Verify expected tools are registered."""

    EXPECTED_TOOLS = [
        "semantic_search",
        "get_file_skeleton",
        "get_impact_radius",
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

    def test_index_status_is_resource(self):
        assert "index_status" not in _get_tool_names()
        assert "coderay://index/status" in _get_resource_uris()


class TestIndexStatus:
    @patch("coderay.mcp_server.server._load_state")
    def test_no_state_raises(self, mock_state):
        from coderay.mcp_server.server import index_status

        mock_state.return_value = None
        with pytest.raises(IndexNotBuiltError):
            index_status()


class TestGetFileSkeleton:
    def test_missing_file_raises(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        with pytest.raises(FileNotFoundError):
            get_file_skeleton(str(tmp_path / "nope.py"))

    def test_real_file(self, tmp_path):
        """Read a file within workspace."""
        from coderay.mcp_server.server import get_file_skeleton

        with patch("coderay.mcp_server.server._resolve_index_dir") as mock_idx:
            mock_idx.return_value = tmp_path / ".coderay"
            f = tmp_path / "hello.py"
            f.write_text("def greet(): pass")
            result = get_file_skeleton("hello.py")
            assert "def greet" in result

    def test_path_traversal_rejected(self, tmp_path):
        """Paths outside workspace (e.g. ../../secrets) are rejected."""
        from coderay.mcp_server.server import get_file_skeleton

        with patch("coderay.mcp_server.server._resolve_index_dir") as mock_idx:
            mock_idx.return_value = tmp_path / ".coderay"
            with pytest.raises(FileNotFoundError):
                get_file_skeleton("../../etc/passwd")


class TestSemanticSearch:
    @patch("coderay.mcp_server.server._get_retrieval")
    @patch("coderay.mcp_server.server._load_state")
    def test_no_state_raises(self, mock_state, mock_retrieval):
        from coderay.mcp_server.server import semantic_search

        mock_state.return_value = None
        with pytest.raises(IndexNotBuiltError):
            semantic_search("hello")


class TestGetImpactRadius:
    @patch("coderay.mcp_server.server._load_graph")
    def test_no_graph_raises(self, mock_graph):
        from coderay.mcp_server.server import get_impact_radius

        mock_graph.return_value = None
        with pytest.raises(IndexNotBuiltError):
            get_impact_radius("node")

    @patch("coderay.mcp_server.server._load_graph")
    def test_response_envelope(self, mock_load):
        from coderay.mcp_server.server import get_impact_radius

        g = MagicMock()
        g.get_impact_radius.return_value = ImpactResult(resolved_node="node", nodes=[])
        mock_load.return_value = g
        result = get_impact_radius("node")
        assert isinstance(result, dict)
        assert "results" in result
        assert result["resolved_node"] == "node"
