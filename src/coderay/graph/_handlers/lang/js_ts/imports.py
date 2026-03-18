"""JS/TS import handler."""

from __future__ import annotations

from typing import Any

from coderay.core.models import EdgeKind, GraphEdge
from coderay.graph._utils import resolve_relative_import

TSNode = Any


class JsTsImportHandler:
    """Handle JS/TS import_statement: import { x } from './foo', import * as X from 'pkg'."""

    def handle(self, node: TSNode, parser: Any) -> None:
        """Process JS/TS import node."""
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
            return

        raw_source = parser.node_text(source_node).strip()
        if (
            len(raw_source) >= 2
            and raw_source[0] in ("'", '"')
            and raw_source[-1] == raw_source[0]
        ):
            raw_source = raw_source[1:-1]
        if not raw_source:
            return

        if raw_source.startswith(("./", "../")):
            mod_path = resolve_relative_import(parser._module_id, raw_source)
        else:
            mod_path = raw_source.replace("/", ".")
        if not mod_path:
            return

        import_clause = node.child_by_field_name("import_clause") or next(
            (c for c in node.children if c.type == "import_clause"), None
        )
        imported = self._collect_imported(import_clause, mod_path, parser)
        if not imported:
            return

        self._emit_edges(imported, mod_path, parser)

    def _collect_imported(
        self, import_clause: TSNode | None, mod_path: str, parser: Any
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
                        local = (
                            parser.node_text(alias_node).strip() if alias_node else orig
                        )
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

    def _emit_edges(
        self,
        imported: list[tuple[str, str]],
        mod_path: str,
        parser: Any,
    ) -> None:
        is_excluded = mod_path in parser._excluded_modules
        for original, local in imported:
            qualified = f"{mod_path}::{original}" if original != mod_path else mod_path
            parser._file_ctx.register_import(local, qualified)
            if is_excluded:
                continue
            resolved_target = parser._file_ctx.resolve(local)
            edge_target = resolved_target if resolved_target else qualified
            parser._edges.append(
                GraphEdge(
                    source=parser._module_id,
                    target=edge_target,
                    kind=EdgeKind.IMPORTS,
                )
            )
