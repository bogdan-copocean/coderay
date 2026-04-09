"""JS/TS import_statement — Pass 2 emission."""

from __future__ import annotations

from coderay.graph.facts import Fact, ImportsEdge
from coderay.graph.handlers.js_ts.import_binder import parse_jsts_imports
from coderay.graph.lowering.name_bindings import NameBindings
from coderay.graph.refs import infer_import_target_kind
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class JsTsImportEmitter:
    """Emit ImportsEdge facts for JS/TS imports (Pass 2)."""

    def emit(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: NameBindings,
    ) -> list[Fact]:
        del scope_stack
        result = parse_jsts_imports(node, parser)
        if result is None:
            return []
        imported, mod_path, module_id = result
        lang = parser.lang_cfg.name
        facts: list[Fact] = []
        for original, local in imported:
            qualified = f"{mod_path}::{original}" if original != mod_path else mod_path
            resolved = bindings.resolve(local)
            tgt = resolved or qualified
            facts.append(
                ImportsEdge(
                    source_id=module_id,
                    target=tgt,
                    source_lang=lang,
                    target_kind=infer_import_target_kind(tgt),
                )
            )
        return facts
