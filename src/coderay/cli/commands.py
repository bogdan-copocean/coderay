from __future__ import annotations

import logging
import os
import sys
import time
import warnings
from pathlib import Path

import click
from dotenv import load_dotenv

from coderay.cli.search_input import SearchInput, resolve_result_paths
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
    for name in (
        "httpx",
        "httpcore",
        "fastembed",
        "huggingface_hub",
        "huggingface_hub.file_download",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    warnings.filterwarnings(
        "ignore",
        message="Cannot enable progress bars: environment variable",
        category=UserWarning,
        module="huggingface_hub.utils.tqdm",
    )


def _set_repo_root(repo_root: Path) -> None:
    from coderay.core.config import ENV_REPO_ROOT

    os.environ[ENV_REPO_ROOT] = str(repo_root.resolve())


def _load_config_or_exit(ctx: click.Context):
    """Load config for ``.coderay.toml`` in the current working directory."""
    from coderay.core.config import ProjectNotInitializedError, get_config

    root = Path.cwd().resolve()
    try:
        _set_repo_root(root)
        return get_config(root)
    except ProjectNotInitializedError as e:
        click.echo(_color(str(e), YELLOW))
        ctx.exit(1)


def _require_built_index(ctx: click.Context, index_dir: Path) -> None:
    if not index_exists(index_dir):
        click.echo(_color("No index found. Run `coderay build` first.", YELLOW))
        ctx.exit(1)
    sm = StateMachine()
    if sm.current_state is None:
        click.echo(_color("No index state. Run `coderay build` first.", YELLOW))
        ctx.exit(1)


@click.group()
@click.version_option(package_name="coderay", prog_name="coderay")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Local semantic code indexer. Start with 'coderay init' then 'coderay watch'."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing .coderay.toml if present.",
)
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    """Initialize a repository for CodeRay."""
    from coderay.core.config import render_default_toml

    repo_root = Path.cwd().resolve()
    _set_repo_root(repo_root)
    cfg_path = repo_root / ".coderay.toml"
    index_dir = repo_root / ".coderay"

    if cfg_path.exists() and not force:
        click.echo(
            _color(
                f"Config already exists at {cfg_path}. Use --force to overwrite.",
                YELLOW,
            )
        )
        ctx.exit(1)

    index_dir.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(render_default_toml(repo_root), encoding="utf-8")
    click.echo(_color(f"Wrote {cfg_path}", GREEN))
    click.echo(_color(f"Index directory: {index_dir}", CYAN))


@cli.command()
@click.option("--full", is_flag=True, help="Full rebuild (clear and re-index)")
@click.pass_context
def build(ctx: click.Context, full: bool) -> None:
    """Build or rebuild index."""
    config = _load_config_or_exit(ctx)
    root = Path.cwd().resolve()
    index_dir = Path(config.index.path)
    index_dir.mkdir(parents=True, exist_ok=True)
    indexer = Indexer(root)
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
@click.option(
    "--top-k", "top_k", default=5, help="Number of results to return (default 5)."
)
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
    """Search by intent (e.g. where auth or retries are handled)."""
    from coderay.core.index_workspace import resolve_index_workspace

    config = _load_config_or_exit(ctx)
    index_dir = Path(config.index.path)
    _require_built_index(ctx, index_dir)
    current_state = StateMachine().current_state

    root = Path.cwd().resolve()
    workspace = resolve_index_workspace(root, config)
    retrieval = Retrieval()
    click.echo(_color(f"Searching: {query_text!r}", CYAN))

    if current_state is None:
        click.echo(_color("No index metadata found. Build index first.", RED))
        ctx.exit(1)
        return

    search_input = SearchInput(
        config=config,
        query=query_text,
        top_k=top_k,
        path_prefix=path_prefix,
        include_tests=include_tests,
    )
    with timed_phase("search", log=False) as tp:
        results = retrieval.search(search_input.to_dto(), current_state)
    click.echo(_color(f"Query took {tp.elapsed:.2f}s", BOLD))

    if not results:
        click.echo(_color("No results.", YELLOW))
        return

    for i, r in enumerate(resolve_result_paths(results, workspace), 1):
        preview = (r.content or "")[:200].replace("\n", " ")
        if len(r.content or "") > 200:
            preview += "..."
        click.echo("")
        line = (
            f"  {i}. {r.path}:{r.start_line}-{r.end_line} ({r.symbol} "
            f"score: {r.score:.3f} relevance: {r.relevance})"
        )
        click.echo(_color(line, GREEN))
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
    """Show indexed chunks. Use --by-file for a file summary."""
    config = _load_config_or_exit(ctx)
    index_dir = Path(config.index.path)
    _require_built_index(ctx, index_dir)

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
    from coderay.state.version import read_index_version
    from coderay.storage.lancedb import Store

    config = _load_config_or_exit(ctx)
    index_dir = Path(config.index.path)
    _require_built_index(ctx, index_dir)
    sm = StateMachine()
    state = sm.current_state

    if state is None:
        click.echo(_color("No index metadata found.", RED))
        ctx.exit(1)
        return

    store = Store()
    chunks = store.chunk_count()
    version = read_index_version(index_dir)

    click.echo(_color("Index Status", BOLD))
    click.echo(f"  State:          {state.state.value}")
    click.echo("  Sources:")
    for s in state.sources:
        role = "primary" if s.is_primary else s.alias
        c = s.commit[:12] if s.commit else "?"
        click.echo(f"    [{role}] {s.branch or '?'} @ {c}")
    click.echo(f"  Chunks:         {chunks}")
    click.echo(f"  Files tracked:  {len(sm.file_hashes)}")
    click.echo(f"  Schema version: {version or '?'}")


@cli.command()
@click.pass_context
def maintain(ctx: click.Context) -> None:
    """Reclaim space and compact index."""
    config = _load_config_or_exit(ctx)
    root = Path.cwd().resolve()
    index_dir = Path(config.index.path)
    _require_built_index(ctx, index_dir)
    click.echo(_color("Maintaining index...", CYAN))
    indexer = Indexer(root)
    with acquire_indexer_lock(index_dir):
        result = indexer.maintain()
    if result.get("cleanup_done"):
        click.echo(_color("Cleaned up old versions", GREEN))
    if result.get("compact_done"):
        click.echo(_color("Compacted fragments", GREEN))
    if not result:
        click.echo(_color("Nothing to maintain", CYAN))


@cli.command()
@click.argument("file_path", type=str)
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
@click.option(
    "--lines",
    "line_range",
    default=None,
    metavar="START-END",
    help=(
        "File line range (1-based inclusive); keep only symbols fully within this span. "
        "Do not combine with a :START-END suffix on FILE_PATH (same meaning)."
    ),
)
def skeleton(
    file_path: str,
    include_imports: bool,
    symbol: str | None,
    line_range: str | None,
) -> None:
    """Print signatures without bodies (cheaper than reading the full file)."""
    from coderay.skeleton.extractor import extract_skeleton
    from coderay.skeleton.path_range import (
        parse_file_line_range,
        parse_skeleton_file_arg,
    )

    try:
        path_str, rng_from_path = parse_skeleton_file_arg(file_path, parse_suffix=True)
    except ValueError as e:
        raise click.BadParameter(str(e)) from e
    file_line_range = rng_from_path
    if line_range:
        if file_line_range is not None:
            raise click.UsageError(
                "Use either a path ending with :START-END or --lines, not both."
            )
        try:
            file_line_range = parse_file_line_range(line_range)
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="--lines") from e
    resolved = Path(path_str)
    if not resolved.is_file():
        raise click.BadParameter(f"not a file: {path_str}", param_hint="file_path")
    content = resolved.read_text(encoding="utf-8", errors="replace")
    out = extract_skeleton(
        resolved,
        content,
        include_imports=include_imports,
        symbol=symbol,
        line_range=file_line_range,
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
    """List call/import graph edges. Filter with --from, --to, --kind."""
    from coderay.graph.builder import load_graph

    config = _load_config_or_exit(ctx)
    index_dir = Path(config.index.path)
    _require_built_index(ctx, index_dir)
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
@click.argument("symbol", required=True, metavar="SYMBOL")
@click.option(
    "--max-depth",
    "max_depth",
    default=2,
    help="How many caller/dependent levels to traverse (default 2).",
)
@click.pass_context
def impact_cmd(ctx: click.Context, symbol: str, max_depth: int) -> None:
    """Show callers and dependents of SYMBOL.

    SYMBOL can be a fully qualified node ID (e.g. 'src/models.py::User.save')
    or a bare name (e.g. 'parse_config') if it is unambiguous in the graph.
    """
    from coderay.core.index_workspace import resolve_index_workspace
    from coderay.graph.builder import load_graph

    config = _load_config_or_exit(ctx)
    root = Path.cwd().resolve()
    index_dir = Path(config.index.path)
    _require_built_index(ctx, index_dir)
    graph = load_graph(index_dir)
    if graph is None:
        click.echo(_color("No graph data. Run 'coderay build' to build it.", YELLOW))
        ctx.exit(1)
    workspace = resolve_index_workspace(root, config)
    result = graph.get_impact_radius(symbol, depth=max_depth)
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
        logical = r.get("file_path", "?")
        try:
            path = str(workspace.resolve_logical(logical))
        except (KeyError, ValueError):
            path = logical
        name = r.get("name", "?")
        start = r.get("start_line", "")
        end = r.get("end_line", "")
        loc = f":{start}-{end}" if start and end else ""
        click.echo(f"  {i}. {path}{loc}::{name}")


@cli.command()
@click.option(
    "--quiet",
    is_flag=True,
    help="Suppress per-file output; show only update summaries.",
)
@click.pass_context
def watch(
    ctx: click.Context,
    quiet: bool,
) -> None:
    """Watch for changes; re-index automatically."""
    from coderay.core.index_workspace import resolve_index_workspace
    from coderay.pipeline.watcher import FileWatcher

    config = _load_config_or_exit(ctx)
    root = Path.cwd().resolve()
    index_dir = Path(config.index.path)
    index_dir.mkdir(parents=True, exist_ok=True)

    if quiet:
        logging.getLogger("coderay.pipeline.watcher").setLevel(logging.WARNING)

    indexer = Indexer(root)
    try:
        _require_built_index(ctx, index_dir)
    except Exception as e:
        indexer.error(str(e))
        click.echo(_color(f"Error: {e}", RED))
        raise

    workspace = resolve_index_workspace(root, config)
    watcher = FileWatcher(
        workspace,
        debounce_seconds=float(config.watcher.debounce),
    )
    click.echo(
        _color(
            f"Watching {root} (debounce={config.watcher.debounce}s, Ctrl+C to stop)",
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
