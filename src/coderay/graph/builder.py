from __future__ import annotations

import json
import logging
from pathlib import Path

from coderay.core.config import get_config
from coderay.graph.code_graph import CodeGraph
from coderay.graph.extractor import build_module_filter, extract_graph_from_file

logger = logging.getLogger(__name__)

GRAPH_FILENAME = "graph.json"


def build_graph(
    repo_root: str | Path,
    file_paths_and_contents: list[tuple[str, str]],
) -> CodeGraph:
    """Extract a CodeGraph from the given files.

    Returns:
        Built CodeGraph with resolved edges.
    """
    excluded = build_module_filter()
    graph = CodeGraph()
    for file_path, content in file_paths_and_contents:
        try:
            nodes, edges = extract_graph_from_file(
                file_path, content, excluded_modules=excluded
            )
            graph.add_nodes_and_edges(nodes, edges)
        except Exception as exc:
            logger.warning("Graph extraction failed for %s: %s", file_path, exc)
    resolved = graph.resolve_edges()
    pruned = graph.prune_phantom_edges()
    logger.info(
        "Graph built: %d nodes, %d edges (%d resolved, %d phantoms pruned)",
        graph.node_count,
        graph.edge_count,
        resolved,
        pruned,
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


def _read_files(
    repo: Path,
    paths: list[str],
) -> list[tuple[str, str]]:
    """Read source files from disk, skipping unreadable ones."""
    result: list[tuple[str, str]] = []
    for p in paths:
        full = repo / p
        if full.is_file():
            try:
                content = full.read_text(encoding="utf-8", errors="replace")
                result.append((p, content))
            except Exception as e:
                logger.warning("Could not read %s for graph: %s", p, e)
    return result


def build_and_save_graph(
    repo_root: str | Path,
    changed_paths: list[str] | None = None,
    *,
    files_content: list[tuple[str, str]] | None = None,
) -> None:
    """Build or incrementally update the graph, then save.

    Args:
        repo_root: Repository root directory.
        changed_paths: Paths that changed (incremental mode), or ``None``
            for a full rebuild.
        files_content: Pre-read ``(path, content)`` pairs.  When provided
            the builder skips reading these files from disk, avoiding
            redundant I/O when the caller (e.g. the indexer pipeline)
            already has the contents in memory.
    """
    from coderay.state.machine import StateMachine

    repo = Path(repo_root)
    config = get_config()
    idx_dir = Path(config.index.path)

    existing_graph = load_graph(idx_dir) if changed_paths else None
    incremental = existing_graph is not None and changed_paths is not None

    if changed_paths is not None:
        paths_to_parse = changed_paths
    else:
        from coderay.parsing.languages import get_supported_extensions

        supported = get_supported_extensions()
        sm = StateMachine()
        paths_to_parse = [
            p for p in sm.file_hashes if any(p.endswith(ext) for ext in supported)
        ]

    if files_content is not None:
        provided_paths = {p for p, _ in files_content}
        missing = [p for p in paths_to_parse if p not in provided_paths]
        files_with_content = list(files_content)
        if missing:
            files_with_content.extend(_read_files(repo, missing))
    else:
        files_with_content = _read_files(repo, paths_to_parse)

    if incremental:
        excluded = build_module_filter()
        for fp in paths_to_parse:
            existing_graph.remove_file(fp)
        for fp, content in files_with_content:
            try:
                nodes, edges = extract_graph_from_file(
                    fp, content, excluded_modules=excluded
                )
                existing_graph.add_nodes_and_edges(nodes, edges)
            except Exception as exc:
                logger.warning("Graph extraction failed for %s: %s", fp, exc)
        existing_graph.resolve_edges()
        existing_graph.prune_phantom_edges()
        graph = existing_graph
        logger.info(
            "Graph incremental update: re-parsed %d files",
            len(files_with_content),
        )
    else:
        graph = build_graph(repo_root, files_with_content)

    save_graph(graph, idx_dir)
    logger.info(
        "Graph: saved %d nodes, %d edges from %d files",
        graph.node_count,
        graph.edge_count,
        len(files_with_content) if not incremental else graph.node_count,
    )
