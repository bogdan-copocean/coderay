from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import click
from dotenv import load_dotenv

from coderay.core.lock import acquire_indexer_lock
from coderay.core.timing import timed_phase
from coderay.pipeline.indexer import Indexer
from coderay.retrieval.search import Retrieval
from coderay.state.machine import StateMachine
from coderay.storage.lancedb import Store, index_exists

# Load .env so configuration and environment variables are available.
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
    # Suppress noisy HTTP logging; keep only warnings and errors
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


@click.group()
@click.version_option(package_name="coderay", prog_name="coderay")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """CodeRay — build, update, search, inspect index."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    from coderay.core.config import get_config

    get_config()


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
    """Build or rebuild index."""
    from coderay.core.config import get_config

    config = get_config()
    index_dir = Path(config.index.path)
    index_dir.mkdir(parents=True, exist_ok=True)
    indexer = Indexer(repo)
    try:
        with timed_phase("build", log=False) as tp:
            with acquire_indexer_lock(index_dir):
                if full:
                    click.echo(_color("Building full index...", CYAN))
                    result = indexer.build_full()
                else:
                    if not indexer.index_exists():
                        click.echo(_color("Building full index...", CYAN))
                    else:
                        click.echo(_color("Updating index (incremental)...", CYAN))
                    result = indexer.ensure_index()
            indexer.maintain()
        click.echo(_color(f"{result} in {tp.elapsed:.2f}s", GREEN))
    except Exception as e:
        indexer.error(str(e))
        click.echo(_color(f"Error: {e}", RED))
        raise


@cli.command()
@click.argument("query_text", required=True)
@click.option("--top-k", "top_k", default=5, help="Number of results (default 5)")
@click.option("--path-prefix", help="Filter to files under this directory")
@click.option(
    "--include-tests/--no-tests",
    "include_tests",
    default=True,
    help="Include test files in results (default: true)",
)
@click.pass_context
def search_cmd(
    ctx: click.Context,
    query_text: str,
    top_k: int,
    path_prefix: str | None,
    include_tests: bool,
) -> None:
    """Semantic search."""
    from coderay.core.config import get_config

    config = get_config()
    index_dir = Path(config.index.path)
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    sm = StateMachine()
    current_state = sm.current_state
    if current_state is None:
        click.echo(_color("No index state. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    retrieval = Retrieval()
    click.echo(_color(f"Searching: {query_text!r}", CYAN))

    with timed_phase("search", log=False) as tp:
        results = retrieval.search(
            query=query_text,
            current_state=current_state,
            top_k=top_k,
            path_prefix=path_prefix,
            include_tests=include_tests,
        )
    click.echo(_color(f"Query took {tp.elapsed:.2f}s", BOLD))

    if not results:
        click.echo(_color("No results.", YELLOW))
        return

    for i, r in enumerate(results, 1):
        preview = (r.content or "")[:200].replace("\n", " ")
        if len(r.content or "") > 200:
            preview += "..."
        click.echo("")
        click.echo(
            _color(f"  {i}. {r.path}:{r.start_line}-{r.end_line} ({r.symbol})", GREEN)
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
    """Show index contents: chunk counts and/or list."""
    from coderay.core.config import get_config

    config = get_config()
    index_dir = Path(config.index.path)
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    store = Store()
    total = store.chunk_count()
    click.echo(_color(f"Total chunks: {total}", CYAN))

    if by_file:
        by_path = store.chunks_by_path()
        for path in sorted(by_path.keys()):
            count = by_path[path]
            click.echo(f"  {path}: {count}")
        return

    chunks = store.list_chunks(limit=chunk_limit, path_prefix=path_prefix)
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
    """Show index status."""
    from coderay.core.config import get_config
    from coderay.state.version import read_index_version
    from coderay.storage.lancedb import Store

    config = get_config()
    index_dir = Path(config.index.path)
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)

    sm = StateMachine()
    state = sm.current_state
    if state is None:
        click.echo(_color("No index state found.", YELLOW))
        ctx.exit(1)

    store = Store()
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
    """Reclaim space and compact index."""
    from coderay.core.config import get_config

    config = get_config()
    index_dir = Path(config.index.path)
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)
    click.echo(_color("Maintaining index...", CYAN))
    indexer = Indexer(repo)
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
@click.option(
    "--include-imports",
    is_flag=True,
    default=False,
    help="Include import statements in the skeleton.",
)
@click.option(
    "--symbol",
    type=str,
    default=None,
    help="Filter to a specific class or top-level function by name.",
)
def skeleton(
    file_path: Path,
    include_imports: bool,
    symbol: str | None,
) -> None:
    """Print API skeleton (signatures, no bodies)."""
    from coderay.skeleton.extractor import extract_skeleton

    content = file_path.read_text(encoding="utf-8", errors="replace")
    out = extract_skeleton(
        file_path, content, include_imports=include_imports, symbol=symbol
    )
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
    """List call and import graph edges."""
    from coderay.core.config import get_config
    from coderay.graph.builder import load_graph

    config = get_config()
    index_dir = Path(config.index.path)
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)
    graph = load_graph(index_dir)
    edges = graph.to_dict().get("edges", []) if graph else []
    if not edges:
        click.echo(
            _color(
                "No graph data. Run 'coderay build' to build it.",
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


@cli.command("impact")
@click.argument("node_id", required=True)
@click.option(
    "--max-depth",
    "max_depth",
    default=2,
    help="How many caller/dependent levels to traverse (default 2).",
)
@click.pass_context
def impact_cmd(ctx: click.Context, node_id: str, max_depth: int) -> None:
    """List blast radius (callers and dependents)."""
    from coderay.core.config import get_config
    from coderay.graph.builder import load_graph

    config = get_config()
    index_dir = Path(config.index.path)
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run 'coderay build' first.", YELLOW))
        ctx.exit(1)
    graph = load_graph(index_dir)
    if graph is None:
        click.echo(_color("No graph data. Run 'coderay build' to build it.", YELLOW))
        ctx.exit(1)
    result = graph.get_impact_radius(node_id, depth=max_depth)
    out = result.to_dict()
    resolved = out.get("resolved_node")
    if resolved:
        click.echo(_color(f"Resolved: {resolved}", CYAN))
    results = out.get("results", [])
    if not results:
        click.echo(_color("No callers or dependents found.", YELLOW))
        if out.get("hint"):
            click.echo(out["hint"])
        return
    click.echo(_color(f"Callers/dependents ({len(results)}):", CYAN))
    for i, r in enumerate(results, 1):
        path = r.get("file_path", "?")
        name = r.get("name", "?")
        start = r.get("start_line", "")
        end = r.get("end_line", "")
        loc = f":{start}-{end}" if start and end else ""
        click.echo(f"  {i}. {path}{loc}::{name}")


@cli.command()
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, path_type=Path),
    help="Repo root",
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
    quiet: bool,
) -> None:
    """Watch for changes; re-index automatically."""
    from coderay.core.config import get_config
    from coderay.pipeline.watcher import FileWatcher

    config = get_config()
    index_dir = Path(config.index.path)
    index_dir.mkdir(parents=True, exist_ok=True)

    if quiet:
        logging.getLogger("coderay.pipeline.watcher").setLevel(logging.WARNING)

    indexer = Indexer(repo)
    try:
        with timed_phase("watch_startup", log=False) as tp:
            with acquire_indexer_lock(index_dir):
                if not indexer.index_exists():
                    click.echo(_color("No index found. Building full index...", CYAN))
                result = indexer.ensure_index()
            indexer.maintain()
        click.echo(_color(f"{result} in {tp.elapsed:.2f}s", GREEN))
    except Exception as e:
        indexer.error(str(e))
        click.echo(_color(f"Error: {e}", RED))
        raise

    watcher = FileWatcher(repo, index_dir)
    click.echo(
        _color(
            f"Watching {repo.resolve()} "
            f"(debounce={config.watcher.debounce}s, Ctrl+C to stop)",
            CYAN,
        )
    )

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
    """Entry point for coderay CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
