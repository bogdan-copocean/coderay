"""Post-merge graph passes: global structural cleanup, then per-language passes."""

from __future__ import annotations

import logging

# Side-effect: ensures language plugins are registered before passes run.
import coderay.graph.extractors.js_ts  # noqa: F401
import coderay.graph.extractors.python  # noqa: F401
from coderay.graph.code_graph import CodeGraph
from coderay.graph.passes.global_passes import run_global_passes

logger = logging.getLogger(__name__)

__all__ = ["run_global_passes", "run_post_merge_pipeline"]


def run_post_merge_pipeline(
    graph: CodeGraph, langs: set[str] | None = None
) -> tuple[int, int]:
    """Run global passes then registered per-language passes.

    ``langs`` restricts which language passes run; None means all languages
    represented in the graph (derived from file paths via the language registry).
    Returns (rewritten, pruned).
    """
    from coderay.graph.language_plugin import registered_languages, run_passes

    run_global_passes(graph)
    rewritten = pruned = 0
    targets = langs if langs is not None else set(registered_languages())
    for lang in targets:
        r, p = run_passes(lang, graph)
        rewritten += r
        pruned += p
    return rewritten, pruned
