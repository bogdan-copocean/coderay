from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from coderay.graph.code_graph import CodeGraph
from coderay.graph.extractor import GraphExtractor

logger = logging.getLogger(__name__)

GRAPH_FILENAME = "graph.json"


def build_graph(
    repo_root: str | Path,
    file_paths_and_contents: list[tuple[str, str]],
    config: dict[str, Any] | None = None,
) -> CodeGraph:
    """Extract a CodeGraph from the given files.

    Returns:
        Built CodeGraph with resolved edges.
    """
    extractor = GraphExtractor(config=config)
    graph = CodeGraph()
    for file_path, content in file_paths_and_contents:
        try:
            nodes, edges = extractor.extract_from_file(file_path, content)
            graph.add_nodes_and_edges(nodes, edges)
        except Exception as exc:
            logger.warning("Graph extraction failed for %s: %s", file_path, exc)
    resolved = graph.resolve_edges()
    logger.info(
        "Graph built: %d nodes, %d edges (%d call edges resolved)",
        graph.node_count,
        graph.edge_count,
        resolved,
    )
    return graph


def save_graph(graph: CodeGraph, index_dir: str | Path) -> Path:
    """Persist the graph to index_dir/graph.json."""
    path = Path(index_dir) / GRAPH_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph.to_dict(), indent=2))
    logger.info("Saved graph to %s", path)
    return path


def load_graph(index_dir: str | Path) -> CodeGraph | None:
    """Load a previously-saved graph, or None if it doesn't exist."""
    path = Path(index_dir) / GRAPH_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return CodeGraph.from_dict(data)
    except Exception as exc:
        logger.warning("Failed to load graph from %s: %s", path, exc)
        return None


def build_and_save_graph(
    repo_root: str | Path,
    index_dir: str | Path,
    changed_paths: list[str] | None = None,
) -> None:
    """Build or incrementally update the graph, then save."""
    from coderay.core.config import load_config
    from coderay.state.machine import StateMachine

    repo = Path(repo_root)
    idx_dir = Path(index_dir)
    config = load_config(idx_dir)

    existing_graph = load_graph(idx_dir) if changed_paths else None
    incremental = existing_graph is not None and changed_paths is not None

    if changed_paths is not None:
        paths_to_parse = changed_paths
    else:
        from coderay.chunking.registry import get_supported_extensions

        supported = get_supported_extensions()
        sm = StateMachine(idx_dir)
        paths_to_parse = [
            p for p in sm.file_hashes if any(p.endswith(ext) for ext in supported)
        ]

    files_with_content: list[tuple[str, str]] = []
    for p in paths_to_parse:
        full = repo / p
        if full.is_file():
            try:
                content = full.read_text(encoding="utf-8", errors="replace")
                files_with_content.append((p, content))
            except Exception as e:
                logger.warning("Could not read %s for graph: %s", p, e)

    if incremental:
        extractor = GraphExtractor(config=config)
        for fp in paths_to_parse:
            existing_graph.remove_file(fp)
        for fp, content in files_with_content:
            try:
                nodes, edges = extractor.extract_from_file(fp, content)
                existing_graph.add_nodes_and_edges(nodes, edges)
            except Exception as exc:
                logger.warning("Graph extraction failed for %s: %s", fp, exc)
        existing_graph.resolve_edges()
        graph = existing_graph
        logger.info(
            "Graph incremental update: re-parsed %d files",
            len(files_with_content),
        )
    else:
        graph = build_graph(repo_root, files_with_content, config=config)

    save_graph(graph, idx_dir)
    logger.info(
        "Graph: saved %d nodes, %d edges from %d files",
        graph.node_count,
        graph.edge_count,
        len(files_with_content) if not incremental else graph.node_count,
    )
