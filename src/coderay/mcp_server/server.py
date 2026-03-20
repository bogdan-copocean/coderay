from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from coderay.core.config import get_config
from coderay.mcp_server.errors import IndexNotBuiltError

logger = logging.getLogger(__name__)


mcp = FastMCP(
    name="coderay",
    instructions=(
        "CodeRay provides semantic code search, file skeletons, and "
        "dependency impact analysis over a pre-built index.\n"
        "\n"
        "- semantic_search: search code by meaning. Best for "
        "'how/where' questions. Use grep for exact symbol lookup.\n"
        "- get_file_skeleton: signatures and docstrings only, no bodies. "
        "Useful to check a file's API before reading full source. "
        "Works without the index.\n"
        "- get_impact_radius: reverse dependency traversal from the code "
        "graph. Shows callers/dependents of a function or class.\n"
        "\n"
        "All tools except get_file_skeleton require a built index. "
        "On index errors, ask the user to run 'coderay build'."
    ),
)

_retrieval_cache: dict[Path, Any] = {}
_state_machine_cache: dict[Path, Any] = {}


def _resolve_index_dir() -> Path:
    """Resolve index directory to absolute path."""
    return Path(get_config().index.path).resolve()


def _get_retrieval():
    """Return cached Retrieval instance."""
    idx = _resolve_index_dir()
    if idx not in _retrieval_cache:
        from coderay.retrieval.search import Retrieval

        _retrieval_cache[idx] = Retrieval()
    return _retrieval_cache[idx]


def _load_graph():
    """Load code graph from disk; None if absent."""
    from coderay.graph.builder import load_graph

    return load_graph(_resolve_index_dir())


def _get_state_machine():
    """Return cached StateMachine instance."""
    idx = _resolve_index_dir()
    if idx not in _state_machine_cache:
        from coderay.state.machine import StateMachine

        _state_machine_cache[idx] = StateMachine()
    return _state_machine_cache[idx]


def _load_state():
    """Load IndexMeta state; None if no run completed."""
    return _get_state_machine().current_state


READ_ONLY_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


@mcp.tool(
    description=(
        "Search code by meaning. Returns chunks ranked by relevance, "
        "each with path, line range, symbol, score, content, and a "
        "relevance tier ('high', 'medium', or 'low'). "
        "Best for 'how/where' questions; use grep for exact symbols or keywords."
        "Any phrase with less than 3 words will return an error."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    tags={"search"},
)
def semantic_search(
    query: Annotated[
        str,
        Field(
            description="Natural language question about the code (no keyword search)."
        ),
    ],
    top_k: int = 5,
    path_prefix: Annotated[
        str | None,
        Field(
            description=(
                "Filter to files under this directory, e.g. 'src/coderay/graph/'"
            ),
        ),
    ] = None,
    include_tests: Annotated[
        bool,
        Field(
            description=(
                "Include test files in results. Set to false to see "
                "only production code."
            ),
        ),
    ] = True,
) -> dict:
    """Search semantic index."""
    retrieval = _get_retrieval()
    state = _load_state()
    if state is None:
        raise IndexNotBuiltError()

    results = retrieval.search(
        query=query,
        current_state=state,
        top_k=top_k,
        path_prefix=path_prefix,
        include_tests=include_tests,
    )
    return {"results": [r.to_dict() for r in results]}


@mcp.tool(
    description=(
        "Extracts class/function signatures and docstrings from a "
        "file — no bodies. Output is significantly shorter than "
        "full source. Does not require the index."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    tags={"analysis"},
)
def get_file_skeleton(
    file_path: Annotated[
        str,
        Field(description="Absolute or relative path to the file"),
    ],
    include_imports: Annotated[
        bool,
        Field(
            description="Include import statements in the skeleton. "
            "Defaults to false; pass true to include imports.",
        ),
    ] = False,
    symbol: Annotated[
        str | None,
        Field(
            description=(
                "Filter to a specific class or top-level function by name, "
                "e.g. 'MyClass' or 'parse_config'."
            ),
        ),
    ] = None,
) -> str:
    """Get file API surface (signatures, no bodies)."""
    from coderay.skeleton.extractor import extract_skeleton

    workspace_root = _resolve_index_dir().parent.resolve()
    candidate = (workspace_root / file_path).resolve()
    try:
        candidate.relative_to(workspace_root)
    except ValueError:
        raise FileNotFoundError(f"File not found: {file_path}")
    if not candidate.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    content = candidate.read_text(encoding="utf-8", errors="replace")
    return extract_skeleton(
        candidate, content, include_imports=include_imports, symbol=symbol
    )


@mcp.tool(
    description=(
        "Reverse dependency traversal: lists callers and dependents "
        "of a function or class from the code graph. "
        "Static analysis only — blind spots include DI containers "
        "(e.g. inject.instance()), dynamic dispatch, and untyped "
        "factory returns. Supplement with grep for these patterns."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    tags={"analysis"},
)
def get_impact_radius(
    node_id: Annotated[
        str,
        Field(
            description=(
                "Fully qualified node ID, e.g. "
                "'src/utils.py::parse_config' or "
                "'src/models.py::User.save'"
            ),
        ),
    ],
    max_depth: Annotated[
        int,
        Field(description="How many caller/dependent levels to traverse"),
    ] = 2,
) -> dict:
    """Analyze blast radius of changing function or module."""
    graph = _load_graph()
    if graph is None:
        raise IndexNotBuiltError(
            "No graph found. Ask the user to run 'coderay build' "
            "in their terminal, then retry."
        )
    return graph.get_impact_radius(node_id, depth=max_depth).to_dict()


@mcp.resource(
    "coderay://index/status",
    description=("Index status: build state, branch, commit, and chunk count."),
    tags={"status"},
)
def index_status() -> dict:
    """Check index health and status."""
    state = _load_state()
    if state is None:
        raise IndexNotBuiltError()

    from coderay.state.version import read_index_version
    from coderay.storage.lancedb import index_exists as idx_exists

    idx_dir = _resolve_index_dir()
    has_store = idx_exists(idx_dir)
    chunk_count = 0
    if has_store:
        from coderay.storage.lancedb import Store

        store = Store()
        chunk_count = store.chunk_count()

    return {
        "status": state.state.value,
        "branch": state.branch,
        "last_commit": state.last_commit,
        "chunk_count": chunk_count,
        "schema_version": read_index_version(idx_dir),
        "has_store": has_store,
    }


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
