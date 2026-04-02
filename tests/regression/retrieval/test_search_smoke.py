"""Smoke tests: verify search returns expected symbols for known queries.

These tests run against the real CodeRay index (this repo). They require:
  1. A built index: `coderay build`
  2. A real embedder at query time (fastembed recommended for CI)

Skip when no index exists. Skip when embedder resolves to `mlx` (query embed
can abort in headless runs; set `embedder.backend = fastembed` to run smoke).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from coderay.core.config import ENV_REPO_ROOT, _reset_config_for_testing, get_config
from coderay.embedding.backend_resolve import resolved_embedder_backend

REPO_ROOT = Path(__file__).resolve().parents[3]
INDEX_DIR = REPO_ROOT / ".coderay"

pytestmark = pytest.mark.regression

skip_no_index = pytest.mark.skipif(
    not (INDEX_DIR / "chunks.lance").exists(),
    reason="No built index — run `coderay build` first",
)


@pytest.fixture(scope="module", autouse=True)
def _skip_smoke_when_mlx_backend():
    """Query-time MLX embed can abort in headless/CI; smoke uses CPU fastembed."""
    prev = os.environ.get(ENV_REPO_ROOT)
    os.environ[ENV_REPO_ROOT] = str(REPO_ROOT)
    _reset_config_for_testing(None)
    try:
        cfg = get_config(REPO_ROOT)
        if resolved_embedder_backend(cfg.embedder.backend) == "mlx":
            pytest.skip(
                "embedder resolves to mlx; use fastembed for automated smoke "
                "(set embedder.backend = fastembed in .coderay.toml)"
            )
    finally:
        _reset_config_for_testing(None)
        if prev is None:
            os.environ.pop(ENV_REPO_ROOT, None)
        else:
            os.environ[ENV_REPO_ROOT] = prev


def _search(query: str, top_k: int = 5) -> list[dict]:
    """Run a search against the real index."""
    from coderay.cli.search_input import SearchInput
    from coderay.core.config import (
        ENV_REPO_ROOT,
        _reset_config_for_testing,
        get_config,
    )
    from coderay.retrieval.search import Retrieval
    from coderay.state.machine import StateMachine

    prev = os.environ.get(ENV_REPO_ROOT)
    os.environ[ENV_REPO_ROOT] = str(REPO_ROOT)
    _reset_config_for_testing(None)

    try:
        config = get_config(REPO_ROOT)
        sm = StateMachine()
        state = sm.current_state
        if state is None:
            pytest.skip("No index state")

        retrieval = Retrieval()
        search_input = SearchInput(config=config, query=query, top_k=top_k)
        results = retrieval.search(search_input.to_dto(), state)
        return [r.to_dict() for r in results]
    finally:
        _reset_config_for_testing(None)
        if prev is None:
            os.environ.pop(ENV_REPO_ROOT, None)
        else:
            os.environ[ENV_REPO_ROOT] = prev


SMOKE_CASES = [
    (
        "how are files re-indexed on change",
        ["update_incremental", "files_with_changed_content"],
    ),
    (
        "how does semantic search work",
        ["search", "Retrieval", "semantic_search"],
    ),
    (
        "how does the skeleton extractor work",
        ["extract_skeleton", "SkeletonTreeSitterParser"],
    ),
    (
        "how does the code graph find callers",
        ["get_impact_radius", "CodeGraph"],
    ),
    (
        "how does the file watcher detect changes",
        ["FileWatcher", "start", "_on_change"],
    ),
    (
        "how are chunks embedded",
        ["embed", "LocalEmbedder", "MLXEmbedder"],
    ),
    (
        "how does config loading work",
        ["get_config", "Config", "config_for_repo"],
    ),
    (
        "how does lancedb store chunks",
        ["Store", "insert_chunks", "search"],
    ),
    (
        "how does hybrid search combine results",
        ["hybrid", "search", "bm25"],
    ),
    (
        "how does the MCP server expose tools",
        ["semantic_search", "get_file_skeleton"],
    ),
    (
        "how does tree-sitter parse python",
        ["_python_language", "_make_parser", "get_parse_context"],
    ),
    (
        "how does the state machine track build progress",
        ["StateMachine", "IndexMeta", "finish"],
    ),
]


@skip_no_index
@pytest.mark.parametrize(
    "query,expected_any",
    SMOKE_CASES,
    ids=[case[0][:40] for case in SMOKE_CASES],
)
def test_search_returns_expected_symbol(query: str, expected_any: list[str]):
    """Verify at least one expected symbol appears in top-5."""
    results = _search(query, top_k=5)
    assert results, f"No results for query: {query!r}"

    found_symbols = [r["symbol"] for r in results]
    found_content = " ".join(r.get("content", "") for r in results)
    match = any(
        sym in found_symbols or sym.lower() in found_content.lower()
        for sym in expected_any
    )
    assert match, (
        f"Query: {query!r}\n"
        f"Expected any of: {expected_any}\n"
        f"Got symbols: {found_symbols}"
    )
