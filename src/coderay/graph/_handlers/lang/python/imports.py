"""Python import handler."""

from __future__ import annotations

from typing import Any

from coderay.core.models import EdgeKind, GraphEdge
from coderay.graph._utils import resolve_relative_import

TSNode = Any


class PythonImportHandler:
    """Handle Python import_from_statement, import_statement, future_import_statement."""

    def handle(
        self, node: TSNode, parser: Any, *, scope_stack: list[str] | None = None
    ) -> None:
        """Process Python import node."""
        ntype = node.type
        module: list[str] = []
        imported: list[tuple[str, str]] = []
        # scope_stack → caller: lazy imports inside a function scope to that function
        caller_id = parser._caller_id_from_scope(scope_stack or [])

        # Walk child tokens to extract module path and imported names.
        # Three forms: "from X import Y", "import X", "from __future__ import Y"
        for child in node.children:
            prev = child.prev_sibling
            prev_type = prev.type if prev else None

            if ntype == "import_from_statement":
                # "from X import Y" — token after "from" is the module path
                if prev_type == "from":
                    text = self._resolve_import_text(child, parser)
                    if text:
                        module.append(text)
                    continue
                if child.type == "wildcard_import":
                    continue
                self._collect_import_name(child, imported, parser)

            elif ntype == "import_statement":
                # "import os, json" — each dotted_name after "import" or ","
                if prev_type == "import" or prev_type == ",":
                    self._collect_bare_import(child, module, imported, parser)

            elif ntype == "future_import_statement":
                if prev_type == "from":
                    module.append(parser.node_text(child).strip())
                    continue
                self._collect_import_name(child, imported, parser)

        # Bare imports emit their own edges (one per dotted name);
        # from-imports emit edges per imported symbol.
        if ntype != "import_statement":
            self._emit_from_import_edges(module, imported, ntype, parser, caller_id)
        if ntype == "import_statement":
            self._emit_bare_import_edges(imported, parser, caller_id)

    def _resolve_import_text(self, child: TSNode, parser: Any) -> str | None:
        text = parser.node_text(child).strip()
        if text and text[0] == ".":
            return resolve_relative_import(parser._module_id, text)
        return text or None

    def _collect_import_name(
        self, child: TSNode, names: list[tuple[str, str]], parser: Any
    ) -> None:
        ctype = child.type
        if ctype in ("dotted_name", "identifier"):
            name = parser.node_text(child).strip()
            names.append((name, name))
        elif ctype == "aliased_import":
            original, alias = self._parse_aliased_import(child, parser)
            if original:
                names.append((original, alias or original))

    def _collect_bare_import(
        self,
        child: TSNode,
        module: list[str],
        imported: list[tuple[str, str]],
        parser: Any,
    ) -> None:
        ctype = child.type
        if ctype == "dotted_name":
            text = self._resolve_import_text(child, parser)
            if text:
                module.append(text)
                local = text.split(".")[0]
                imported.append((text, local))
        elif ctype == "aliased_import":
            original, alias = self._parse_aliased_import(child, parser)
            if original:
                text = original
                if text and text[0] == ".":
                    text = resolve_relative_import(parser._module_id, text) or text
                local = alias or text.split(".")[0]
                module.append(text)
                imported.append((text, local))

    def _parse_aliased_import(
        self, node: TSNode, parser: Any
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

    def _emit_from_import_edges(
        self,
        module: list[str],
        imported: list[tuple[str, str]],
        ntype: str,
        parser: Any,
        caller_id: str | None = None,
    ) -> None:
        if not module or not imported:
            return
        source = caller_id or parser._module_id
        mod_name = module[0]
        is_excluded = mod_name in parser._excluded_modules
        for original, local in imported:
            qualified = f"{mod_name}::{original}"
            if ntype != "future_import_statement":
                parser._file_ctx.register_import(local, qualified)
            if is_excluded:
                continue
            resolved_target = parser._file_ctx.resolve(local)
            edge_target = resolved_target if resolved_target else qualified
            parser._edges.append(
                GraphEdge(
                    source=source,
                    target=edge_target,
                    kind=EdgeKind.IMPORTS,
                )
            )

    def _emit_bare_import_edges(
        self,
        imported: list[tuple[str, str]],
        parser: Any,
        caller_id: str | None = None,
    ) -> None:
        source = caller_id or parser._module_id
        for mod_text, local in imported:
            parser._file_ctx.register_import(local, mod_text)
            if mod_text in parser._excluded_modules:
                continue
            resolved_target = parser._file_ctx.resolve(local)
            edge_target = resolved_target if resolved_target else mod_text
            parser._edges.append(
                GraphEdge(
                    source=source,
                    target=edge_target,
                    kind=EdgeKind.IMPORTS,
                )
            )
