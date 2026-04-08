"""Post-merge graph passes: per-language structural cleanup."""

from __future__ import annotations

import logging

# Side-effect: ensures language plugins are registered before passes run.
import coderay.graph.extractors.js_ts  # noqa: F401
import coderay.graph.extractors.python  # noqa: F401
from coderay.graph.code_graph import CodeGraph

logger = logging.getLogger(__name__)

__all__ = ["run_post_merge_pipeline"]


def run_post_merge_pipeline(
    graph: CodeGraph, langs: set[str] | None = None
) -> tuple[int, int]:
    """Run registered per-language post-merge passes.

    ``langs`` restricts which language passes run; None runs all registered.
    Returns (rewritten, pruned).
    """
    from coderay.graph.language_plugin import registered_languages, run_passes

    rewritten = pruned = 0
    targets = langs if langs is not None else set(registered_languages())
    for lang in targets:
        r, p = run_passes(lang, graph)
        rewritten += r
        pruned += p
    return rewritten, pruned
