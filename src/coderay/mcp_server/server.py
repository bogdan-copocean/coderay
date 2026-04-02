from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from coderay.cli.search_input import SearchInput, resolve_result_paths
from coderay.core.config import ProjectNotInitializedError, get_config
from coderay.mcp_server.errors import IndexNotBuiltError

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
for _name in ("fastembed", "huggingface_hub", "huggingface_hub.file_download"):
    logging.getLogger(_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


mcp = FastMCP(
    name="coderay",
    instructions=(
        "CodeRay augments grep — it does not replace it. "
        "For exact symbol or string lookup, use grep/ripgrep. "
        "CodeRay answers the questions grep can't: intent, structure, dependencies.\n"
        "\n"
        "- semantic_search: search code by meaning. Best for "
        "'how/where' questions. Use grep for exact symbol lookup.\n"
        "- get_file_skeleton: signatures and docstrings only, no bodies. "
        "Check a file's API before reading full source. "
        "Works without the index.\n"
        "- get_impact_radius: reverse dependency traversal from the code "
        "graph. Shows callers/dependents of a function or class. "
        "Accepts a bare name (e.g. 'parse_config') if unambiguous; "
        "returns candidates on ambiguity.\n"
        "\n"
        "All tools except get_file_skeleton require a built index. "
        "On index errors, ask the user to run 'coderay build'. "
        "If results seem stale, ask them to run 'coderay status' first."
    ),
)

_retrieval_cache: dict[Path, Any] = {}
_state_machine_cache: dict[Path, Any] = {}
_cache_lock = asyncio.Lock()


def _resolve_index_dir() -> Path:
    """Resolve index directory to absolute path."""
    try:
        return Path(get_config().index.path).resolve()
    except ProjectNotInitializedError as e:
        raise IndexNotBuiltError(str(e)) from e


async def _get_retrieval():
    """Return cached Retrieval instance (async-safe)."""
    idx = _resolve_index_dir()
    async with _cache_lock:
        if idx not in _retrieval_cache:
            from coderay.retrieval.search import Retrieval

            _retrieval_cache[idx] = await asyncio.to_thread(Retrieval)
        return _retrieval_cache[idx]


async def _load_graph():
    """Load code graph from disk; None if absent."""
    from coderay.graph.builder import load_graph

    return await asyncio.to_thread(load_graph, _resolve_index_dir())


async def _get_state_machine():
    """Return cached StateMachine instance (async-safe)."""
    idx = _resolve_index_dir()
    async with _cache_lock:
        if idx not in _state_machine_cache:
            from coderay.state.machine import StateMachine

            _state_machine_cache[idx] = await asyncio.to_thread(StateMachine)
        return _state_machine_cache[idx]


async def _load_state():
    """Load IndexMeta state; None if no run completed."""
    return (await _get_state_machine()).current_state


READ_ONLY_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


@mcp.tool(
    description=(
        "Search the codebase by meaning. Best for intent-based questions like "
        "'where is auth handled' or 'how are embeddings loaded'. Returns chunks "
        "ranked by relevance with path, line range, symbol, score, content, and "
        "relevance tier ('high', 'medium', 'low'). "
        "For exact symbols or identifiers, prefer grep — it is faster and more precise."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    tags={"search"},
)
async def semantic_search(
    query: Annotated[
        str,
        Field(description="Natural language question about the code."),
    ],
    top_k: Annotated[
        int,
        Field(description="Number of results to return (default 5)."),
    ] = 5,
    repos: Annotated[
        list[str] | None,
        Field(
            description=(
                "Repo aliases to scope the search, e.g. ['my-service']. "
                "Pass ['*'] for workspace-wide. "
                "Omit to use search.default_scope from config. "
                "See index status for available aliases."
            ),
        ),
    ] = None,
    path_prefix: Annotated[
        str | None,
        Field(
            description=(
                "Further filter to files under this sub-directory, e.g. 'src/graph/'."
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
    retrieval = await _get_retrieval()
    state = await _load_state()
    if state is None:
        raise IndexNotBuiltError()

    from coderay.core.index_workspace import resolve_index_workspace

    cfg = get_config()
    search_input = SearchInput(
        config=cfg,
        query=query,
        top_k=top_k,
        repos=repos,
        path_prefix=path_prefix,
        include_tests=include_tests,
    )
    results = await asyncio.to_thread(
        retrieval.search, request=search_input.to_dto(), current_state=state
    )
    workspace = resolve_index_workspace(_resolve_index_dir().parent, cfg)
    return {"results": [r.to_dict() for r in resolve_result_paths(results, workspace)]}


@mcp.tool(
    description=(
        "Extracts class/function signatures and docstrings from a file — "
        "no bodies. Significantly fewer tokens than reading the full source "
        "(a 500-line file typically compresses to ~100 lines of skeleton). "
        "Use this before deciding whether to read a file in full. "
        "Does not require the index."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    tags={"analysis"},
)
async def get_file_skeleton(
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
    content = await asyncio.to_thread(
        candidate.read_text, encoding="utf-8", errors="replace"
    )
    return await asyncio.to_thread(
        extract_skeleton,
        candidate,
        content,
        include_imports=include_imports,
        symbol=symbol,
    )


@mcp.tool(
    description=(
        "Reverse dependency traversal: lists callers and dependents "
        "of a function or class from the code graph. "
        "Static analysis only — blind spots include DI containers "
        "(e.g. inject.instance(), @inject.autoparams under stacked decorators), "
        "dynamic dispatch, and untyped factory returns. "
        "Supplement with grep for these patterns."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    tags={"analysis"},
)
async def get_impact_radius(
    node_id: Annotated[
        str,
        Field(
            description=(
                "Node to analyse. Accepts a fully qualified ID "
                "('src/utils.py::parse_config', 'src/models.py::User.save') "
                "or a bare name ('parse_config') if it is unambiguous in the graph. "
                "On ambiguity, the tool returns a list of candidates to choose from."
            ),
        ),
    ],
    max_depth: Annotated[
        int,
        Field(description="How many caller/dependent levels to traverse"),
    ] = 2,
) -> dict:
    """Analyze blast radius of changing function or module."""
    graph = await _load_graph()
    if graph is None:
        raise IndexNotBuiltError(
            "No graph found. Ask the user to run 'coderay build' "
            "in their terminal, then retry."
        )
    result = await asyncio.to_thread(graph.get_impact_radius, node_id, depth=max_depth)
    out: dict[str, Any] = result.to_dict()
    return out


@mcp.resource(
    "coderay://index/status",
    description=("Index status: build state, branch, commit, and chunk count."),
    tags={"status"},
)
async def index_status() -> dict:
    """Check index health and status."""
    state = await _load_state()
    if state is None:
        raise IndexNotBuiltError()

    from coderay.state.version import read_index_version
    from coderay.storage.lancedb import index_exists as idx_exists

    idx_dir = _resolve_index_dir()
    has_store = await asyncio.to_thread(idx_exists, idx_dir)
    chunk_count = 0
    if has_store:
        from coderay.storage.lancedb import Store

        store = Store()
        chunk_count = await asyncio.to_thread(store.chunk_count)

    primary = state.primary()
    version = await asyncio.to_thread(read_index_version, idx_dir)
    return {
        "status": state.state.value,
        "branch": primary.branch if primary else None,
        "last_commit": primary.commit if primary else None,
        "sources": [
            {
                "alias": s.alias,
                "branch": s.branch,
                "commit": s.commit,
                "is_primary": s.is_primary,
            }
            for s in state.sources
        ],
        "chunk_count": chunk_count,
        "schema_version": version,
        "has_store": has_store,
    }


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
