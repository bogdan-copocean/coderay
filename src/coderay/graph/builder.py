from __future__ import annotations

import json
import logging
from pathlib import Path

from coderay.core.config import get_config
from coderay.core.models import EdgeKind, GraphEdge
from coderay.graph.code_graph import CodeGraph
from coderay.graph.extractor import (
    build_module_filter,
    build_module_index,
    extract_graph_from_file,
)

logger = logging.getLogger(__name__)

GRAPH_FILENAME = "graph.json"


def build_graph(
    repo_root: str | Path,
    file_paths_and_contents: list[tuple[str, str]],
) -> CodeGraph:
    """Extract CodeGraph from files; resolve and prune phantom edges."""
    excluded = build_module_filter()
    all_paths = [fp for fp, _ in file_paths_and_contents]
    module_index = build_module_index(all_paths)

    graph = CodeGraph()
    for file_path, content in file_paths_and_contents:
        try:
            nodes, edges = extract_graph_from_file(
                file_path,
                content,
                excluded_modules=excluded,
                module_index=module_index,
            )
            graph.add_nodes_and_edges(nodes, edges)
        except Exception as exc:
            logger.exception("Graph extraction failed for %s: %s", file_path, exc)
            raise

    rewritten = _rewrite_package_phantom_targets(graph)
    pruned = _prune_phantom_calls(graph)
    logger.info(
        "Graph built: %d nodes, %d edges (%d phantoms rewritten, %d pruned)",
        graph.node_count,
        graph.edge_count,
        rewritten,
        pruned,
    )
    return graph


def _rewrite_package_phantom_targets(graph: CodeGraph) -> int:
    """Rewrite package::Symbol phantom targets to real node IDs."""
    rewritten = 0
    to_rewrite: list[tuple[str, str, str]] = []  # (source, old_target, new_target)

    for u, v, data in graph.iter_edges():
        if data.get("kind") != EdgeKind.CALLS:
            continue
        if graph.get_node(v) is not None:
            continue
        if "::" not in v:
            continue
        qualified = v.split("::", 1)[-1]
        if not qualified:
            continue
        resolved = graph.resolve_symbol(qualified)
        if not resolved or resolved == v:
            continue
        if graph.get_node(resolved) is None:
            continue
        to_rewrite.append((u, v, resolved))

    for u, v, new_target in to_rewrite:
        graph.remove_edge(u, v)
        graph.add_edge(GraphEdge(source=u, target=new_target, kind=EdgeKind.CALLS))
        rewritten += 1

    if rewritten:
        logger.info("Rewrote %d package phantom CALLS targets", rewritten)
    return rewritten


def _prune_phantom_calls(graph: CodeGraph) -> int:
    """Remove CALLS edges to unresolvable phantom targets.

    Prunes two categories:
    1. Phantoms with zero resolution candidates (no matching symbol).
    2. Ambiguous bare-name phantoms (no ``::`` or ``.`` in target) where
       multiple candidates exist — these are unresolvable and create noise.
    """
    to_remove = []
    for u, v, data in graph.iter_edges():
        if data.get("kind") != EdgeKind.CALLS:
            continue
        if graph.get_node(v) is not None:
            continue
        if not graph.has_symbol_candidates(v):
            to_remove.append((u, v))
        elif "::" not in v and "." not in v and graph.has_ambiguous_symbol(v):
            to_remove.append((u, v))

    for u, v in to_remove:
        graph.remove_edge(u, v)

    graph.remove_orphan_phantoms()

    if to_remove:
        logger.info("Pruned %d phantom CALLS edges", len(to_remove))
    return len(to_remove)


def save_graph(graph: CodeGraph, index_dir: str | Path) -> Path:
    """Save graph to index_dir/graph.json."""
    path = Path(index_dir) / GRAPH_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph.to_dict(), indent=2))
    logger.info("Saved graph to %s", path)
    return path


def load_graph(index_dir: str | Path) -> CodeGraph | None:
    """Load saved graph, or None if missing."""
    path = Path(index_dir) / GRAPH_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return CodeGraph.from_dict(data)
    except Exception as exc:
        logger.warning("Failed to load graph from %s: %s", path, exc)
        return None


def _read_files(repo: Path, paths: list[str]) -> list[tuple[str, str]]:
    """Read source files from disk; skip unreadable."""
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
    """Build or incrementally update graph, then save."""
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
        # For incremental builds, we need indexes from ALL known files
        all_paths = list(existing_graph.all_file_paths())
        for fp in paths_to_parse:
            existing_graph.remove_file(fp)
        # Add back the changed paths for the index
        changed_set = set(paths_to_parse)
        all_paths = [p for p in all_paths if p not in changed_set]
        all_paths.extend(fp for fp, _ in files_with_content)
        module_index = build_module_index(all_paths)
        for fp, content in files_with_content:
            try:
                nodes, edges = extract_graph_from_file(
                    fp,
                    content,
                    excluded_modules=excluded,
                    module_index=module_index,
                )
                existing_graph.add_nodes_and_edges(nodes, edges)
            except Exception as exc:
                logger.exception("Graph extraction failed for %s: %s", fp, exc)
                raise
        _rewrite_package_phantom_targets(existing_graph)
        _prune_phantom_calls(existing_graph)
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
