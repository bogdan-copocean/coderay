"""JavaScript/TypeScript CST -> graph facts."""

from __future__ import annotations

from coderay.graph.extractors.base import BaseGraphExtractor
from coderay.graph.processors.js_ts.import_processor import JsTsImportProcessor
from coderay.graph.processors.js_ts.type_lookup import JsTsTypeLookup
from coderay.graph.processors.type_lookup import TypeLookup


class JsTsGraphExtractor(BaseGraphExtractor):
    """Lower JS/TS tree-sitter CST to graph facts."""

    _import_processor_cls = JsTsImportProcessor

    def _build_type_lookup(self) -> TypeLookup:
        return JsTsTypeLookup(self._session, self, self._find_class_node)
