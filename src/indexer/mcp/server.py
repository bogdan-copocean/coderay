"""FastMCP server exposing semantic code index tools.

Run with: index-mcp (stdio transport, for Claude Code integration)
or:       index-mcp --sse (SSE transport, for development/debugging)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("semantic-code-indexer")

DEFAULT_INDEX_DIR = ".index"

_retrieval_cache: dict[Path, Any] = {}
_state_machine_cache: dict[Path, Any] = {}


def _resolve_index_dir(index_dir: str | None = None) -> Path:
    return Path(index_dir or DEFAULT_INDEX_DIR).resolve()


def _get_retrieval(index_dir: str | None = None):
    idx = _resolve_index_dir(index_dir)
    if idx not in _retrieval_cache:
        from indexer.retrieval.search import Retrieval

        _retrieval_cache[idx] = Retrieval(idx)
    return _retrieval_cache[idx]


def _load_graph(index_dir: str | None = None):
    from indexer.graph.builder import load_graph

    return load_graph(_resolve_index_dir(index_dir))


def _get_state_machine(index_dir: str | None = None):
    idx = _resolve_index_dir(index_dir)
    if idx not in _state_machine_cache:
        from indexer.state.machine import StateMachine

        _state_machine_cache[idx] = StateMachine(idx)
    return _state_machine_cache[idx]


def _load_state(index_dir: str | None = None):
    return _get_state_machine(index_dir).current_state


@mcp.tool()
def semantic_search(
    query: str,
    top_k: int = 10,
    path_prefix: str | None = None,
    language: str | None = None,
    index_dir: str | None = None,
) -> str:
    """Search code by meaning. Returns the most semantically similar code chunks.

    Args:
        query: Natural language description of what you're looking for.
        top_k: Number of results to return (default 10).
        path_prefix: Filter to files under this directory.
        language: Filter to a specific language (python, typescript, javascript, go).
        index_dir: Path to the index directory (default: .index).
    """
    retrieval = _get_retrieval(index_dir)
    state = _load_state(index_dir)
    if state is None:
        return json.dumps({"error": "No index state found. Run 'index build' first."})
    try:
        results = retrieval.search(
            query,
            state,
            top_k=top_k,
            path_prefix=path_prefix,
            language=language,
        )
    except RuntimeError as e:
        return json.dumps({"error": str(e)})
    return json.dumps(results, default=str)


@mcp.tool()
def get_file_skeleton(file_path: str) -> str:
    """Get the API surface of a file — signatures, docstrings, imports; no bodies.

    Useful for understanding a file's interface without reading the full source.

    Args:
        file_path: Path to the source file.
    """
    from indexer.skeleton.extractor import extract_skeleton

    p = Path(file_path)
    if not p.is_file():
        return json.dumps({"error": f"File not found: {file_path}"})
    content = p.read_text(encoding="utf-8", errors="replace")
    return extract_skeleton(p, content)


@mcp.tool()
def trace_callers(
    function_name: str,
    index_dir: str | None = None,
) -> str:
    """Find all functions that call the given function.

    Args:
        function_name: The function name to trace callers for.
        index_dir: Path to the index directory.
    """
    graph = _load_graph(index_dir)
    if graph is None:
        return json.dumps({"error": "No graph found. Run 'index build' first."})
    callers = graph.get_callers(function_name)
    return json.dumps([n.to_dict() for n in callers])


@mcp.tool()
def trace_callees(
    function_name: str,
    index_dir: str | None = None,
) -> str:
    """Find all functions that the given function calls.

    Args:
        function_name: The function name to trace callees for.
        index_dir: Path to the index directory.
    """
    graph = _load_graph(index_dir)
    if graph is None:
        return json.dumps({"error": "No graph found. Run 'index build' first."})
    callees = graph.get_callees(function_name)
    return json.dumps([n.to_dict() for n in callees])


@mcp.tool()
def get_dependencies(
    module_path: str,
    index_dir: str | None = None,
) -> str:
    """Get all modules that this module imports.

    Args:
        module_path: The module file path.
        index_dir: Path to the index directory.
    """
    graph = _load_graph(index_dir)
    if graph is None:
        return json.dumps({"error": "No graph found. Run 'index build' first."})
    deps = graph.get_dependencies(module_path)
    return json.dumps([n.to_dict() for n in deps])


@mcp.tool()
def get_dependents(
    module_path: str,
    index_dir: str | None = None,
) -> str:
    """Get all modules that import this module (reverse dependencies).

    Args:
        module_path: The module file path.
        index_dir: Path to the index directory.
    """
    graph = _load_graph(index_dir)
    if graph is None:
        return json.dumps({"error": "No graph found. Run 'index build' first."})
    dependents = graph.get_dependents(module_path)
    return json.dumps([n.to_dict() for n in dependents])


@mcp.tool()
def get_subclasses(
    class_name: str,
    index_dir: str | None = None,
) -> str:
    """Get all subclasses of a given class.

    Args:
        class_name: The class name to find subclasses for.
        index_dir: Path to the index directory.
    """
    graph = _load_graph(index_dir)
    if graph is None:
        return json.dumps({"error": "No graph found. Run 'index build' first."})
    subclasses = graph.get_subclasses(class_name)
    return json.dumps([n.to_dict() for n in subclasses])


@mcp.tool()
def get_impact_radius(
    node_id: str,
    max_depth: int = 3,
    index_dir: str | None = None,
) -> str:
    """Analyze the blast radius of a change to a function or module.

    Shows all nodes reachable within max_depth hops via calls, imports, etc.

    Args:
        node_id: The node (function or module) to analyze.
        max_depth: Maximum graph traversal depth (default 3).
        index_dir: Path to the index directory.
    """
    graph = _load_graph(index_dir)
    if graph is None:
        return json.dumps({"error": "No graph found. Run 'index build' first."})
    impact = graph.get_impact_radius(node_id, depth=max_depth)
    return json.dumps([n.to_dict() for n in impact])


@mcp.tool()
def index_status(index_dir: str | None = None) -> str:
    """Check the health and status of the semantic index.

    Returns index state, chunk count, last commit, and branch info.

    Args:
        index_dir: Path to the index directory.
    """
    state = _load_state(index_dir)
    if state is None:
        return json.dumps({"status": "no_index", "message": "No index found."})

    from indexer.core.config import get_embedding_dimensions, load_config
    from indexer.state.version import read_index_version
    from indexer.storage.lancedb import index_exists as idx_exists

    idx_dir = _resolve_index_dir(index_dir)
    has_store = idx_exists(idx_dir)
    chunk_count = 0
    if has_store:
        from indexer.storage.lancedb import Store

        config = load_config(idx_dir)
        store = Store(idx_dir, dimensions=get_embedding_dimensions(config))
        chunk_count = store.chunk_count()

    return json.dumps(
        {
            "status": state.state.value,
            "branch": state.branch,
            "last_commit": state.last_commit,
            "chunk_count": chunk_count,
            "schema_version": read_index_version(idx_dir),
            "has_store": has_store,
        },
        default=str,
    )


def main():
    """Entry point for the index-mcp command."""
    import sys

    transport = "stdio"
    if "--sse" in sys.argv:
        transport = "sse"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
