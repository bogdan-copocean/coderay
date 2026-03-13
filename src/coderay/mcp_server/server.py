from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("coderay")

DEFAULT_INDEX_DIR = ".index"

_retrieval_cache: dict[Path, Any] = {}
_state_machine_cache: dict[Path, Any] = {}


def _resolve_index_dir(index_dir: str | None = None) -> Path:
    """Resolve the index directory to an absolute path."""
    return Path(index_dir or DEFAULT_INDEX_DIR).resolve()


def _get_retrieval(index_dir: str | None = None):
    """Return a cached Retrieval instance for the given index directory."""
    idx = _resolve_index_dir(index_dir)
    if idx not in _retrieval_cache:
        from coderay.retrieval.search import Retrieval

        _retrieval_cache[idx] = Retrieval(idx)
    return _retrieval_cache[idx]


def _load_graph(index_dir: str | None = None):
    """Load the code graph from disk, or return None if absent."""
    from coderay.graph.builder import load_graph

    return load_graph(_resolve_index_dir(index_dir))


def _get_state_machine(index_dir: str | None = None):
    """Return a cached StateMachine instance for the given index directory."""
    idx = _resolve_index_dir(index_dir)
    if idx not in _state_machine_cache:
        from coderay.state.machine import StateMachine

        _state_machine_cache[idx] = StateMachine(idx)
    return _state_machine_cache[idx]


def _load_state(index_dir: str | None = None):
    """Load the current IndexMeta state, or None if no run has completed."""
    return _get_state_machine(index_dir).current_state


@mcp.tool
def semantic_search(
    query: str,
    top_k: int = 10,
    path_prefix: str | None = None,
    language: str | None = None,
    index_dir: str | None = None,
) -> str:
    """Search code by meaning."""
    retrieval = _get_retrieval(index_dir)
    state = _load_state(index_dir)
    if state is None:
        return json.dumps({"error": "No index state found. Run 'coderay build' first."})
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
    score_type = results[0].get("score_type", "cosine") if results else "cosine"
    return json.dumps(
        {
            "score_type": score_type,
            "score_description": (
                "cosine similarity (0-1, higher = more similar)"
                if score_type == "cosine"
                else "RRF rank fusion (higher = more relevant, scale differs from cosine)"
            ),
            "results": results,
        },
        default=str,
    )


@mcp.tool
def get_file_skeleton(file_path: str) -> str:
    """Get the API surface of a file (signatures, no bodies)."""
    from coderay.skeleton.extractor import extract_skeleton

    p = Path(file_path)
    if not p.is_file():
        return json.dumps({"error": f"File not found: {file_path}"})
    content = p.read_text(encoding="utf-8", errors="replace")
    return extract_skeleton(p, content)


_STATIC_ANALYSIS_NOTE = (
    "Based on static analysis of source code. Calls through dependency "
    "injection, interfaces, dynamic dispatch (getattr), decorators, or "
    "framework routing may not be detected."
)


@mcp.tool
def get_impact_radius(
    node_id: str,
    max_depth: int = 3,
    index_dir: str | None = None,
) -> str:
    """Analyze the blast radius of changing a function or module."""
    graph = _load_graph(index_dir)
    if graph is None:
        return json.dumps({"error": "No graph found. Run 'coderay build' first."})
    impact = graph.get_impact_radius(node_id, depth=max_depth)
    return json.dumps(
        {
            "results": [n.to_dict() for n in impact],
            "note": _STATIC_ANALYSIS_NOTE,
        }
    )


@mcp.tool
def index_status(index_dir: str | None = None) -> str:
    """Check health and status of the semantic index."""
    state = _load_state(index_dir)
    if state is None:
        return json.dumps({"status": "no_index", "message": "No index found."})

    from coderay.core.config import get_embedding_dimensions, load_config
    from coderay.state.version import read_index_version
    from coderay.storage.lancedb import index_exists as idx_exists

    idx_dir = _resolve_index_dir(index_dir)
    has_store = idx_exists(idx_dir)
    chunk_count = 0
    if has_store:
        from coderay.storage.lancedb import Store

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
    """Entry point for the coderay-mcp command."""
    import sys

    transport = "stdio"
    if "--http" in sys.argv:
        transport = "http"
    elif "--sse" in sys.argv:
        transport = "sse"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
