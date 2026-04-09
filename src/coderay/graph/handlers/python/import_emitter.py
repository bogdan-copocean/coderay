"""Python import_statement / import_from_statement — Pass 2 emission."""

from __future__ import annotations

from coderay.graph.facts import Fact, ImportsEdge
from coderay.graph.handlers.python.import_binder import parse_python_imports
from coderay.graph.lowering.cst_helpers import node_id
from coderay.graph.lowering.name_bindings import NameBindings
from coderay.graph.refs import infer_import_target_kind
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class PythonImportEmitter:
    """Emit ImportsEdge facts for Python imports (Pass 2)."""

    def emit(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: NameBindings,
    ) -> list[Fact]:
        caller_id = node_id(parser.file_path, scope_stack)
        ntype, module, imported = parse_python_imports(node, parser)
        lang = parser.lang_cfg.name

        if ntype == "import_statement":
            facts: list[Fact] = []
            for mod_text, local in imported:
                resolved = bindings.resolve(local)
                tgt = resolved or mod_text
                facts.append(
                    ImportsEdge(
                        source_id=caller_id,
                        target=tgt,
                        source_lang=lang,
                        target_kind=infer_import_target_kind(tgt),
                    )
                )
            return facts

        if not module or not imported:
            return []
        mod_name = module[0]
        facts = []
        for original, local in imported:
            qualified = f"{mod_name}::{original}"
            resolved = bindings.resolve(local)
            tgt = resolved or qualified
            facts.append(
                ImportsEdge(
                    source_id=caller_id,
                    target=tgt,
                    source_lang=lang,
                    target_kind=infer_import_target_kind(tgt),
                )
            )
        return facts
