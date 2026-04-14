"""Tests for MCP server tools: registration, unit (mocked), and integration."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import coderay.mcp_server.server as _srv
from coderay.core.config import (
    ENV_REPO_ROOT,
    _reset_config_for_testing,
    render_default_toml,
)
from coderay.core.models import ImpactResult
from coderay.mcp_server.errors import IndexNotBuiltError
from coderay.mcp_server.server import mcp

# ── Helpers ───────────────────────────────────────────────────────────

_SERVICE_PY = """\
def authenticate(token: str) -> bool:
    \"\"\"Validate an auth token.\"\"\"
    return token == "secret"


class UserService:
    \"\"\"Service for user operations.\"\"\"

    def get_user(self, user_id: int) -> dict:
        \"\"\"Fetch a user by ID.\"\"\"
        return {"id": user_id, "name": "Alice"}
"""


def _get_tool_names() -> set[str]:
    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
    return {t.name for t in tools}


def _get_resource_uris() -> set[str]:
    resources = asyncio.get_event_loop().run_until_complete(mcp.list_resources())
    return {str(r.uri) for r in resources}


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def built_index(fake_git_repo, mock_embedder):
    if fake_git_repo is None:
        pytest.skip("git not available")

    repo: Path = fake_git_repo
    (repo / "service.py").write_text(_SERVICE_PY)
    toml = render_default_toml(repo).replace("dimensions = 384", "dimensions = 4")
    (repo / ".coderay.toml").write_text(toml)

    from coderay.pipeline.indexer import Indexer

    indexer = Indexer(repo, embedder=mock_embedder)
    indexer.build_full()

    cfg = indexer.config
    index_dir = indexer.index_dir

    _reset_config_for_testing(cfg)
    prev_root = os.environ.get(ENV_REPO_ROOT)
    os.environ[ENV_REPO_ROOT] = str(repo)
    _srv._retrieval_cache.clear()
    _srv._state_machine_cache.clear()

    yield repo, index_dir, cfg

    _reset_config_for_testing(None)
    if prev_root is None:
        os.environ.pop(ENV_REPO_ROOT, None)
    else:
        os.environ[ENV_REPO_ROOT] = prev_root
    _srv._retrieval_cache.clear()
    _srv._state_machine_cache.clear()


# ── Tool registration ─────────────────────────────────────────────────


class TestMCPToolsRegistered:
    EXPECTED_TOOLS = ["semantic_search", "get_file_skeleton", "get_impact_radius"]
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


# ── semantic_search ───────────────────────────────────────────────────


class TestSemanticSearch:
    def test_no_state_raises(self):
        from coderay.mcp_server.server import semantic_search

        with (
            patch("coderay.mcp_server.server._get_retrieval", new_callable=AsyncMock),
            patch(
                "coderay.mcp_server.server._load_state", new_callable=AsyncMock
            ) as mock_s,
        ):
            mock_s.return_value = None
            with pytest.raises(IndexNotBuiltError):
                asyncio.run(semantic_search("hello"))

    def test_returns_results_dict(self, built_index, mock_embedder):
        from coderay.mcp_server.server import semantic_search
        from coderay.retrieval.search import Retrieval

        _, _, _ = built_index
        with patch(
            "coderay.mcp_server.server._get_retrieval", new_callable=AsyncMock
        ) as mock_r:
            mock_r.return_value = Retrieval(embedder=mock_embedder)
            result = asyncio.run(semantic_search("authenticate user"))

        assert isinstance(result, dict)
        assert "results" in result

    def test_results_have_expected_fields(self, built_index, mock_embedder):
        from coderay.mcp_server.server import semantic_search
        from coderay.retrieval.search import Retrieval

        _, _, _ = built_index
        with patch(
            "coderay.mcp_server.server._get_retrieval", new_callable=AsyncMock
        ) as mock_r:
            mock_r.return_value = Retrieval(embedder=mock_embedder)
            result = asyncio.run(semantic_search("authenticate user", top_k=3))

        for r in result["results"]:
            assert "path" in r
            assert "score" in r
            assert "symbol" in r
            assert "relevance" in r

    def test_search_input_config_no_attribute_error(self, built_index):
        # Regression: was raising 'SearchInput object has no attribute _config'
        _, _, cfg = built_index
        from coderay.cli.search_input import SearchInput

        si = SearchInput(config=cfg, query="test query", top_k=3)
        assert si.query == "test query"
        assert si.top_k == 3

    def test_search_input_unknown_repo_raises(self, built_index):
        _, _, cfg = built_index
        from coderay.cli.search_input import SearchInput

        with pytest.raises(ValueError, match="Unknown repo alias"):
            SearchInput(config=cfg, query="test", repos=["no-such-alias"])

    def test_search_input_wildcard_skips_validation(self, built_index):
        _, _, cfg = built_index
        from coderay.cli.search_input import SearchInput

        si = SearchInput(config=cfg, query="test", repos=["*"])
        assert si.repos == ["*"]


# ── get_file_skeleton ─────────────────────────────────────────────────


class TestGetFileSkeleton:
    def test_missing_file_raises(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        with pytest.raises(FileNotFoundError):
            asyncio.run(get_file_skeleton(str(tmp_path / "nope.py")))

    def test_real_file(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        with patch("coderay.mcp_server.server._resolve_index_dir") as mock_idx:
            mock_idx.return_value = tmp_path / ".coderay"
            f = tmp_path / "hello.py"
            f.write_text("def greet(): pass")
            result = asyncio.run(get_file_skeleton("hello.py"))
            assert "def greet" in result
            assert str(f.resolve()) in result
            assert f"{f.resolve()}:1-1" in result

    def test_file_line_range_param_narrows(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        with patch("coderay.mcp_server.server._resolve_index_dir") as mock_idx:
            mock_idx.return_value = tmp_path / ".coderay"
            f = tmp_path / "hello.py"
            f.write_text("def greet(): pass")
            result = asyncio.run(get_file_skeleton("hello.py", file_line_range="1-1"))
            assert "def greet" in result

    def test_path_suffix_accepted(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        with patch("coderay.mcp_server.server._resolve_index_dir") as mock_idx:
            mock_idx.return_value = tmp_path / ".coderay"
            f = tmp_path / "hello.py"
            f.write_text("def greet(): pass")
            result = asyncio.run(get_file_skeleton("hello.py:1-1"))
            assert "def greet" in result
            assert str(f.resolve()) in result

    def test_dual_range_spec_raises(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        with patch("coderay.mcp_server.server._resolve_index_dir") as mock_idx:
            mock_idx.return_value = tmp_path / ".coderay"
            (tmp_path / "hello.py").write_text("def greet(): pass")
            with pytest.raises(ValueError):
                asyncio.run(get_file_skeleton("hello.py:1-1", file_line_range="2-2"))

    def test_path_traversal_rejected(self, tmp_path):
        from coderay.mcp_server.server import get_file_skeleton

        with patch("coderay.mcp_server.server._resolve_index_dir") as mock_idx:
            mock_idx.return_value = tmp_path / ".coderay"
            with pytest.raises(FileNotFoundError):
                asyncio.run(get_file_skeleton("../../etc/passwd"))

    def test_full_index_skeleton_includes_all_symbols(self, built_index):
        from coderay.mcp_server.server import get_file_skeleton

        _, index_dir, _ = built_index
        with patch(
            "coderay.mcp_server.server._resolve_index_dir", return_value=index_dir
        ):
            result = asyncio.run(get_file_skeleton("service.py"))

        assert isinstance(result, str)
        assert "authenticate" in result
        assert "UserService" in result

    def test_full_index_symbol_filter(self, built_index):
        from coderay.mcp_server.server import get_file_skeleton

        _, index_dir, _ = built_index
        with patch(
            "coderay.mcp_server.server._resolve_index_dir", return_value=index_dir
        ):
            result = asyncio.run(get_file_skeleton("service.py", symbol="UserService"))

        assert "UserService" in result
        assert "authenticate" not in result


# ── get_impact_radius ─────────────────────────────────────────────────


class TestGetImpactRadius:
    def test_no_graph_raises(self):
        from coderay.mcp_server.server import get_impact_radius

        with patch(
            "coderay.mcp_server.server._load_graph", new_callable=AsyncMock
        ) as mock_g:
            mock_g.return_value = None
            with pytest.raises(IndexNotBuiltError):
                asyncio.run(get_impact_radius("node"))

    def test_response_envelope(self):
        from coderay.mcp_server.server import get_impact_radius

        g = MagicMock()
        g.get_impact_radius.return_value = ImpactResult(resolved_node="node", nodes=[])
        with patch(
            "coderay.mcp_server.server._load_graph", new_callable=AsyncMock
        ) as mock_g:
            mock_g.return_value = g
            result = asyncio.run(get_impact_radius("node"))

        assert isinstance(result, dict)
        assert "results" in result
        assert result["resolved_node"] == "node"

    def test_full_index_returns_impact_dict(self, built_index):
        from coderay.graph.builder import load_graph
        from coderay.mcp_server.server import get_impact_radius

        _, index_dir, _ = built_index
        graph = load_graph(index_dir)
        if graph is None:
            pytest.skip("No graph produced during build")

        with patch(
            "coderay.mcp_server.server._load_graph", new_callable=AsyncMock
        ) as mock_g:
            mock_g.return_value = graph
            result = asyncio.run(get_impact_radius("authenticate"))

        assert isinstance(result, dict)
        assert "resolved_node" in result or "candidates" in result

    def test_full_index_depth_param_accepted(self, built_index):
        from coderay.graph.builder import load_graph
        from coderay.mcp_server.server import get_impact_radius

        _, index_dir, _ = built_index
        graph = load_graph(index_dir)
        if graph is None:
            pytest.skip("No graph produced during build")

        with patch(
            "coderay.mcp_server.server._load_graph", new_callable=AsyncMock
        ) as mock_g:
            mock_g.return_value = graph
            result = asyncio.run(get_impact_radius("authenticate", max_depth=1))

        assert isinstance(result, dict)


# ── index_status ──────────────────────────────────────────────────────


class TestIndexStatus:
    def test_no_state_raises(self):
        from coderay.mcp_server.server import index_status

        with patch(
            "coderay.mcp_server.server._load_state", new_callable=AsyncMock
        ) as mock_s:
            mock_s.return_value = None
            with pytest.raises(IndexNotBuiltError):
                asyncio.run(index_status())

    def test_full_index_returns_status_dict(self, built_index):
        from coderay.mcp_server.server import index_status

        _, index_dir, _ = built_index
        with patch(
            "coderay.mcp_server.server._resolve_index_dir", return_value=index_dir
        ):
            result = asyncio.run(index_status())

        assert isinstance(result, dict)
        for key in ("status", "chunk_count", "has_store", "schema_version"):
            assert key in result

    def test_full_index_has_store(self, built_index):
        from coderay.mcp_server.server import index_status

        _, index_dir, _ = built_index
        with patch(
            "coderay.mcp_server.server._resolve_index_dir", return_value=index_dir
        ):
            result = asyncio.run(index_status())

        assert result["has_store"] is True

    def test_full_index_chunk_count_positive(self, built_index):
        from coderay.mcp_server.server import index_status

        _, index_dir, _ = built_index
        with patch(
            "coderay.mcp_server.server._resolve_index_dir", return_value=index_dir
        ):
            result = asyncio.run(index_status())

        assert result["chunk_count"] > 0
