"""Post-merge graph passes: global then language-tagged."""

from __future__ import annotations

import logging

from coderay.graph.code_graph import CodeGraph
from coderay.graph.extractors.python.passes import run_python_passes
from coderay.graph.passes.global_passes import run_global_passes

logger = logging.getLogger(__name__)


def run_post_merge_pipeline(graph: CodeGraph) -> tuple[int, int]:
    """Run global passes then Python-tagged passes; return (rewritten, pruned)."""
    run_global_passes(graph)
    return run_python_passes(graph)
