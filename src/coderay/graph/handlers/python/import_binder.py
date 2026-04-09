"""Python import_statement / import_from_statement — Pass 1 binding."""

from __future__ import annotations

from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode
from coderay.parsing.conventions import resolve_relative_import


def parse_python_imports(
    node: TSNode, parser: BaseTreeSitterParser
) -> tuple[str, list[str], list[tuple[str, str]]]:
    """Parse import node into (ntype, module_parts, imported_pairs).

    imported_pairs — list of (original_name, local_name).
    """
    ntype = node.type
    module_id = parser.file_path
    module: list[str] = []
    imported: list[tuple[str, str]] = []

    for child in node.children:
        prev = child.prev_sibling
        prev_type = prev.type if prev else None

        if ntype == "import_from_statement":
            if prev_type == "from":
                text = _resolve_import_text(child, module_id, parser)
                if text:
                    module.append(text)
                continue
            if child.type == "wildcard_import":
                continue
            _collect_import_name(child, imported, parser)

        elif ntype == "import_statement":
            if prev_type in ("import", ","):
                _collect_bare_import(child, module, imported, module_id, parser)

        elif ntype == "future_import_statement":
            if prev_type == "from":
                module.append(parser.node_text(child).strip())
                continue
            _collect_import_name(child, imported, parser)

    return ntype, module, imported


class PythonImportBinder:
    """Register Python import names into ``FileNameBindings`` (Pass 1)."""

    def register(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None:
        del scope_stack
        ntype, module, imported = parse_python_imports(node, parser)

        if ntype == "import_statement":
            for mod_text, local in imported:
                # import pkg[.sub]: local "pkg" -> dotted module string (resolved to file in register_import).
                bindings.register_import(local, mod_text)
        else:
            if not module or not imported:
                return
            mod_name = module[0]
            for original, local in imported:
                if ntype != "future_import_statement":
                    # from pkg import X: local "X" -> "pkg::X" (symbol leg resolved in register_import).
                    bindings.register_import(local, f"{mod_name}::{original}")


def _resolve_import_text(
    child: TSNode, module_id: str, parser: BaseTreeSitterParser
) -> str | None:
    text = parser.node_text(child).strip()
    if text and text[0] == ".":
        return resolve_relative_import(module_id, text)
    return text or None


def _collect_import_name(
    child: TSNode, names: list[tuple[str, str]], parser: BaseTreeSitterParser
) -> None:
    ctype = child.type
    if ctype in ("dotted_name", "identifier"):
        name = parser.node_text(child).strip()
        names.append((name, name))
    elif ctype == "aliased_import":
        original, alias = _parse_aliased_import(child, parser)
        if original:
            names.append((original, alias or original))


def _collect_bare_import(
    child: TSNode,
    module: list[str],
    imported: list[tuple[str, str]],
    module_id: str,
    parser: BaseTreeSitterParser,
) -> None:
    ctype = child.type
    if ctype == "dotted_name":
        text = _resolve_import_text(child, module_id, parser)
        if text:
            module.append(text)
            imported.append((text, text.split(".")[0]))
    elif ctype == "aliased_import":
        original, alias = _parse_aliased_import(child, parser)
        if original:
            text = original
            if text and text[0] == ".":
                text = resolve_relative_import(module_id, text) or text
            local = alias or text.split(".")[0]
            module.append(text)
            imported.append((text, local))


def _parse_aliased_import(
    node: TSNode, parser: BaseTreeSitterParser
) -> tuple[str | None, str | None]:
    original: str | None = None
    alias: str | None = None
    for child in node.children:
        if child.type in ("dotted_name", "identifier"):
            if original is None:
                original = parser.node_text(child).strip()
            else:
                alias = parser.node_text(child).strip()
    return original, alias
