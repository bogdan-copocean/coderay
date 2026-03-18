"""JS/TS-specific graph extractor."""

from __future__ import annotations

from coderay.graph.extractor import GraphTreeSitterParser
from coderay.graph.lang_constants import js_ts_lang_constants


class JsTsGraphExtractor:
    """Extract code graph from JS/TS files.

    Uses GraphTreeSitterParser with JS/TS-specific LangConstants.
    """

    def extract(
        self,
        ctx,
        *,
        module_index: dict[str, str],
        excluded_modules: frozenset[str],
    ) -> tuple[list, list]:
        """Return (nodes, edges) for the parsed JS/TS file."""
        parser = GraphTreeSitterParser(
            ctx,
            excluded_modules=excluded_modules,
            module_index=module_index,
            lang_constants=js_ts_lang_constants(),
        )
        return parser.extract()
