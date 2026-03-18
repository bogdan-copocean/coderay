"""Python-specific graph extractor."""

from __future__ import annotations

from coderay.graph.extractor import GraphTreeSitterParser
from coderay.graph.lang_constants import python_lang_constants


class PythonGraphExtractor:
    """Extract code graph from Python files.

    Uses GraphTreeSitterParser with Python-specific LangConstants.
    """

    def extract(
        self,
        ctx,
        *,
        module_index: dict[str, str],
        excluded_modules: frozenset[str],
    ) -> tuple[list, list]:
        """Return (nodes, edges) for the parsed Python file."""
        parser = GraphTreeSitterParser(
            ctx,
            excluded_modules=excluded_modules,
            module_index=module_index,
            lang_constants=python_lang_constants(),
        )
        return parser.extract()
