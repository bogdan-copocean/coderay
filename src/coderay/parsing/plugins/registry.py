"""Registry for language plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from coderay.parsing.plugins.protocol import (
        ChunkerProtocol,
        GraphExtractorProtocol,
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


class _FallbackGraphExtractor:
    """Graph extractor for languages using full lang_cfg (e.g. Go)."""

    def extract(
        self,
        ctx,
        *,
        module_index: dict[str, str],
        excluded_modules: frozenset[str],
    ) -> tuple[list, list]:
        """Extract graph using GraphTreeSitterParser with lang_cfg-derived constants."""
        from coderay.graph.extractor import GraphTreeSitterParser
        from coderay.graph.lang_constants import from_lang_cfg

        parser = GraphTreeSitterParser(
            ctx,
            excluded_modules=excluded_modules,
            module_index=module_index,
            lang_constants=from_lang_cfg(ctx.lang_cfg),
        )
        return parser.extract()


def get_graph_extractor(lang_name: str) -> "GraphExtractorProtocol | None":
    """Return graph extractor plugin for language; None if not implemented."""
    if lang_name == "python":
        from coderay.parsing.plugins.python.graph import PythonGraphExtractor

        return PythonGraphExtractor()
    if lang_name in ("javascript", "typescript"):
        from coderay.parsing.plugins.js_ts.graph import JsTsGraphExtractor

        return JsTsGraphExtractor()
    if lang_name == "go":
        return _FallbackGraphExtractor()
    return None
