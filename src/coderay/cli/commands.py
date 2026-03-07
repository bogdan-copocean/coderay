from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import click
from dotenv import load_dotenv

from coderay.core.lock import acquire_indexer_lock
from coderay.pipeline.indexer import Indexer
from coderay.retrieval.search import Retrieval
from coderay.state.machine import StateMachine
from coderay.storage.lancedb import index_exists

# Load .env so OPENAI_API_KEY etc. are available (e.g. for embedder).
load_dotenv()

# ANSI colors (safe when not TTY we can strip or leave)
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _color(text: str, color: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=level,
        datefmt="%H:%M:%S",
    )
    # Suppress noisy OpenAI/HTTP logging; keep only warnings and errors
    for name in ("openai", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


@click.group()
@click.option("--index-dir", default=".index", help="Index directory (default .index)")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose logging")
@click.pass_context
def cli(ctx: click.Context, index_dir: str, verbose: bool) -> None:
    """CodeRay — build, update, search, and inspect the index."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["index_dir"] = Path(index_dir)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--full", is_flag=True, help="Full rebuild (clear and re-index)")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, path_type=Path),
    help="Repo root",
)
@click.pass_context
def build(ctx: click.Context, full: bool, repo: Path) -> None:
    """Build or rebuild the index."""
    index_dir = ctx.obj["index_dir"]
    index_dir.mkdir(parents=True, exist_ok=True)
    indexer = Indexer(repo, index_dir)
    t0 = time.time()
    try:
        with acquire_indexer_lock(index_dir):
            if full or not indexer.index_exists():
                click.echo(_color("Building full index...", CYAN))
                result = indexer.build_full()
                click.echo(
                    _color(
                        f"{result} in {time.time() - t0:.2f}s",
                        GREEN,
                    )
                )
            else:
                click.echo(_color("Updating index (incremental)...", CYAN))
                result = indexer.update_incremental()
                click.echo(
                    _color(
                        f"{result} in {time.time() - t0:.2f}s",
                        GREEN,
                    )
                )
            indexer.maintain()
    except Exception as e:
        indexer.error(str(e))
        click.echo(_color(f"Error: {e}", RED))
        raise


@cli.command()
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, path_type=Path),
    help="Repo root",
)
@click.pass_context
def update(ctx: click.Context, repo: Path) -> None:
    """Incremental update (only changed files). Uses file lock."""
    index_dir = ctx.obj["index_dir"]
    indexer = Indexer(repo, index_dir)
    t0 = time.time()

    if not indexer.index_exists():
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    try:
        with acquire_indexer_lock(index_dir):
            click.echo(_color("Updating index...", CYAN))
            result = indexer.update_incremental()
            click.echo(_color(f"{result} in {time.time() - t0:.2f}s", GREEN))
            indexer.maintain()
    except Exception as e:
        indexer.error(str(e))
        click.echo(_color(f"Error: {e}", RED))
        raise


@cli.command()
@click.argument("query_text", required=True)
@click.option("--top-k", "top_k", default=10, help="Number of results")
@click.option("--path-prefix", help="Filter by path prefix")
@click.option("--language", help="Filter by language (e.g. python)")
@click.pass_context
def search_cmd(
    ctx: click.Context,
    query_text: str,
    top_k: int,
    path_prefix: str | None,
    language: str | None,
) -> None:
    """Semantic search the index."""
    index_dir = ctx.obj["index_dir"]
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    sm = StateMachine(index_dir)
    current_state = sm.current_state
    if current_state is None:
        click.echo(_color("No index state. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    retrieval = Retrieval(index_dir)
    click.echo(_color(f"Searching: {query_text!r}", CYAN))
    t0 = time.perf_counter()

    results = retrieval.search(
        query=query_text,
        current_state=current_state,
        top_k=top_k,
        path_prefix=path_prefix,
        language=language,
    )
    elapsed = time.perf_counter() - t0
    click.echo(_color(f"Query took {elapsed:.2f}s", BOLD))

    if not results:
        click.echo(_color("No results.", YELLOW))
        return

    score_type = results[0].get("score_type", "cosine")
    if score_type == "rrf":
        click.echo(
            _color("Scoring: hybrid (RRF) — relative ranking, not a percentage", CYAN)
        )
    else:
        click.echo(_color("Scoring: cosine similarity (0-1)", CYAN))

    for i, r in enumerate(results, 1):
        path = r.get("path", "?")
        start = r.get("start_line", 0)
        end = r.get("end_line", 0)
        symbol = r.get("symbol", "?")
        score = r.get("score", 0)
        if score_type == "cosine":
            score_str = f"score={score:.4f} ({score:.0%})"
        else:
            score_str = f"score={score:.4f} (rrf)"
        preview = (r.get("content") or "")[:200].replace("\n", " ")
        if len(r.get("content") or "") > 200:
            preview += "..."
        click.echo("")
        click.echo(
            _color(f"  {i}. {path}:{start}-{end} ({symbol})  {score_str}", GREEN)
        )
        click.echo(f"     {preview}")


@cli.command("list")
@click.option(
    "--by-file",
    is_flag=True,
    help="Show only file path and chunk count (summary view).",
)
@click.option(
    "--limit",
    "chunk_limit",
    default=50,
    help="Max chunks to show when listing (default 50). Ignored if --by-file.",
)
@click.option("--path-prefix", help="Filter by path prefix (e.g. src/).")
@click.option(
    "--show-content",
    is_flag=True,
    help="Include a short content preview per chunk.",
)
@click.pass_context
def list_cmd(
    ctx: click.Context,
    by_file: bool,
    chunk_limit: int,
    path_prefix: str | None,
    show_content: bool,
) -> None:
    """Show what is in the index: chunk counts and/or chunk list."""
    index_dir = ctx.obj["index_dir"]
    retrieval = Retrieval(index_dir)
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    total = retrieval.chunk_count()
    click.echo(_color(f"Total chunks: {total}", CYAN))

    if by_file:
        by_path = retrieval.chunks_by_path()
        for path in sorted(by_path.keys()):
            count = by_path[path]
            click.echo(f"  {path}: {count}")
        return

    chunks = retrieval.list_chunks(limit=chunk_limit, path_prefix=path_prefix)
    for i, row in enumerate(chunks, 1):
        path = row.get("path", "?")
        start = row.get("start_line", 0)
        end = row.get("end_line", 0)
        symbol = row.get("symbol", "?")
        line = f"  {i}. {path}:{start}-{end} ({symbol})"
        click.echo(_color(line, GREEN))
        if show_content:
            content = (row.get("content") or "")[:120].replace("\n", " ")
            if len(row.get("content") or "") > 120:
                content += "..."
            click.echo(f"     {content}")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show index status: state, branch, commit, chunk count."""
    index_dir = ctx.obj["index_dir"]
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    sm = StateMachine(index_dir)
    state = sm.current_state
    if state is None:
        click.echo(_color("No index state found.", YELLOW))
        ctx.exit(1)

    from coderay.core.config import get_embedding_dimensions, load_config
    from coderay.state.version import read_index_version
    from coderay.storage.lancedb import Store

    config = load_config(index_dir)
    store = Store(index_dir, dimensions=get_embedding_dimensions(config))
    chunks = store.chunk_count()
    version = read_index_version(index_dir)

    click.echo(_color("Index Status", BOLD))
    click.echo(f"  State:          {state.state.value}")
    click.echo(f"  Branch:         {state.branch or '?'}")
    click.echo(
        f"  Last commit:    {state.last_commit[:12] if state.last_commit else '?'}"
    )
    click.echo(f"  Chunks:         {chunks}")
    click.echo(f"  Files tracked:  {len(sm.file_hashes)}")
    click.echo(f"  Schema version: {version or '?'}")


@cli.command()
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, path_type=Path),
    help="Repo root",
)
@click.pass_context
def maintain(ctx: click.Context, repo: Path) -> None:
    """Reclaim space and compact the index."""
    index_dir = ctx.obj["index_dir"]
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)
    click.echo(_color("Maintaining index...", CYAN))
    indexer = Indexer(repo, index_dir)
    with acquire_indexer_lock(index_dir):
        result = indexer.maintain()
    if result.get("cleanup_done"):
        click.echo(_color("Cleaned up old versions", GREEN))
    if result.get("compact_done"):
        click.echo(_color("Compacted fragments", GREEN))
    if not result:
        click.echo(_color("Nothing to maintain", CYAN))


@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
def skeleton(file_path: Path) -> None:
    """Print the API skeleton (signatures, no bodies) for a source file."""
    from coderay.skeleton.extractor import extract_skeleton

    content = file_path.read_text(encoding="utf-8", errors="replace")
    out = extract_skeleton(file_path, content)
    click.echo(out)


@cli.command("graph")
@click.option(
    "--kind",
    type=click.Choice(["calls", "imports"]),
    default=None,
    help="Show only this edge kind (default: all).",
)
@click.option(
    "--from",
    "from_node",
    default=None,
    help="Filter: source node contains this string.",
)
@click.option(
    "--to", "to_node", default=None, help="Filter: target node contains this string."
)
@click.option(
    "--limit", type=int, default=200, help="Max edges to print (default 200)."
)
@click.pass_context
def graph_cmd(
    ctx: click.Context,
    kind: str | None,
    from_node: str | None,
    to_node: str | None,
    limit: int,
) -> None:
    """List call and import graph edges (who calls who, who imports what)."""
    index_dir = ctx.obj["index_dir"]
    retrieval = Retrieval(index_dir)
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)
    edges = retrieval.load_graph()
    if not edges:
        click.echo(
            _color(
                "No graph data. Run 'coderay build' or 'coderay update' to build it.",
                YELLOW,
            )
        )
        ctx.exit(0)
    if kind:
        edges = [e for e in edges if e.get("kind") == kind]
    if from_node:
        edges = [e for e in edges if from_node in str(e.get("source", ""))]
    if to_node:
        edges = [e for e in edges if to_node in str(e.get("target", ""))]
    shown = edges[:limit]
    for e in shown:
        click.echo(
            f"  {e.get('source', '')}  --{e.get('kind', '')}-->  {e.get('target', '')}"
        )
    if len(edges) > limit:
        click.echo(_color(f"  ... and {len(edges) - limit} more (use --limit)", CYAN))
    click.echo(_color(f"Total: {len(edges)} edges", CYAN))


@cli.command()
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, path_type=Path),
    help="Repo root",
)
@click.option(
    "--debounce",
    type=float,
    default=None,
    help="Debounce seconds (default from config, typically 2s)",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Suppress per-file output; show only update summaries.",
)
@click.pass_context
def watch(
    ctx: click.Context,
    repo: Path,
    debounce: float | None,
    quiet: bool,
) -> None:
    """Watch for file changes and re-index automatically."""
    from coderay.core.config import load_config
    from coderay.pipeline.watcher import FileWatcher

    index_dir = ctx.obj["index_dir"]
    if not index_exists(index_dir):
        click.echo(
            _color(
                "No index found. Run 'coderay build' first.",
                YELLOW,
            )
        )
        ctx.exit(1)

    config = load_config(index_dir)
    if debounce is not None:
        config.setdefault("watch", {})["debounce_seconds"] = debounce

    if quiet:
        logging.getLogger("coderay.pipeline.watcher").setLevel(logging.WARNING)

    watcher = FileWatcher(repo, index_dir, config=config)

    click.echo(
        _color(
            f"Watching {repo.resolve()} "
            f"(debounce={config.get('watch', {}).get('debounce_seconds', 2)}s, "
            f"Ctrl+C to stop)",
            CYAN,
        )
    )
    # Do an incremental update at start-up
    index_dir = ctx.obj["index_dir"]
    index_dir.mkdir(parents=True, exist_ok=True)
    indexer = Indexer(repo, index_dir)
    indexer.update_incremental()

    watcher.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("")
        click.echo(_color("Stopping watcher...", CYAN))
    finally:
        watcher.stop()
        click.echo(
            _color(
                f"Done. {watcher.update_count} update(s) performed.",
                GREEN,
            )
        )


def main() -> None:
    """Entry point for the ``coderay`` command."""
    cli(obj={})


if __name__ == "__main__":
    main()
