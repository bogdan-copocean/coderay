"""Registry for language plugins (chunker, skeleton).

Graph extraction uses ``get_lang_constants()`` directly — no plugin
dispatch needed; see ``extract_graph_from_file`` in ``graph.extractor``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from coderay.parsing.plugins.protocol import (
        ChunkerProtocol,
        SkeletonProtocol,
    )


def get_chunker(lang_name: str) -> "ChunkerProtocol | None":
    """Return chunker plugin for language; None if not implemented."""
    if lang_name == "python":
        from coderay.parsing.plugins.python.chunker import PythonChunker

        return PythonChunker()
    if lang_name in ("javascript", "typescript"):
        from coderay.parsing.plugins.js_ts.chunker import JsTsChunker

        return JsTsChunker()
    return None


def get_skeleton(lang_name: str) -> "SkeletonProtocol | None":
    """Return skeleton plugin for language; None if not implemented."""
    if lang_name == "python":
        from coderay.parsing.plugins.python.skeleton import PythonSkeleton

        return PythonSkeleton()
    if lang_name in ("javascript", "typescript"):
        from coderay.parsing.plugins.js_ts.skeleton import JsTsSkeleton

        return JsTsSkeleton()
    return None
