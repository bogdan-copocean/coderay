"""JS/TS import_statement — Pass 1 binding."""

from __future__ import annotations

from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode
from coderay.parsing.conventions import resolve_relative_import


def parse_jsts_imports(
    node: TSNode, parser: BaseTreeSitterParser
) -> tuple[list[tuple[str, str]], str, str] | None:
    """Return (imported_pairs, mod_path, module_id) or None if unparseable."""
    source_node = node.child_by_field_name("source")
    if not source_node:
        for child in node.children:
            if child.type == "from_clause":
                source_node = child.child_by_field_name("source")
                break
            if child.type == "string":
                source_node = child
                break
    if not source_node:
        return None

    raw_source = parser.node_text(source_node).strip()
    if (
        len(raw_source) >= 2
        and raw_source[0] in ("'", '"')
        and raw_source[-1] == raw_source[0]
    ):
        raw_source = raw_source[1:-1]
    if not raw_source:
        return None

    module_id = parser.file_path
    if raw_source.startswith(("./", "../")):
        mod_path = resolve_relative_import(module_id, raw_source)
    else:
        mod_path = raw_source.replace("/", ".")
    if not mod_path:
        return None

    import_clause = node.child_by_field_name("import_clause") or next(
        (c for c in node.children if c.type == "import_clause"), None
    )
    imported = _collect_imported(import_clause, mod_path, parser)
    if not imported:
        return None

    return imported, mod_path, module_id


class JsTsImportBinder:
    """Register JS/TS import names into ``FileNameBindings`` (Pass 1)."""

    def register(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None:
        del scope_stack
        result = parse_jsts_imports(node, parser)
        if result is None:
            return
        imported, mod_path, _module_id = result
        for original, local in imported:
            # namespace/default export: (mod_path, mod_path) -> qualified is mod_path only; else mod::orig.
            qualified = f"{mod_path}::{original}" if original != mod_path else mod_path
            bindings.register_import(local, qualified)


def _collect_imported(
    import_clause: TSNode | None,
    mod_path: str,
    parser: BaseTreeSitterParser,
) -> list[tuple[str, str]]:
    imported: list[tuple[str, str]] = []
    if not import_clause:
        return imported

    specs_node = import_clause
    if import_clause.type == "import_clause":
        specs_node = import_clause.child_by_field_name("value") or next(
            (c for c in import_clause.children if c.type == "named_imports"),
            import_clause,
        )

    if specs_node and specs_node.type == "named_imports":
        for spec in specs_node.named_children:
            if spec.type == "import_specifier":
                name_node = spec.child_by_field_name("name")
                alias_node = spec.child_by_field_name("alias")
                orig = parser.node_text(name_node).strip() if name_node else ""
                if orig:
                    local = parser.node_text(alias_node).strip() if alias_node else orig
                    imported.append((orig, local))
    elif import_clause.type == "namespace_import":
        ident = import_clause.child_by_field_name("name")
        if ident:
            local = parser.node_text(ident).strip()
            if local:
                imported.append((mod_path, local))
    elif import_clause.type == "identifier":
        local = parser.node_text(import_clause).strip()
        if local:
            imported.append((mod_path, local))

    return imported
