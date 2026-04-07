"""Python import_statement / import_from_statement lowering."""

from __future__ import annotations

from coderay.graph._utils import resolve_relative_import
from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead
from coderay.graph.processors.imports import append_import_edge
from coderay.graph.processors.scope import caller_id_for_scope
from coderay.parsing.base import TSNode


class PythonImportProcessor:
    """Handle import_from / import / future_import (Python)."""

    def __init__(self, session: LoweringSession, syntax: SyntaxRead) -> None:
        self._session = session
        self._syntax = syntax

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        """Process Python import node."""
        ntype = node.type
        module: list[str] = []
        imported: list[tuple[str, str]] = []
        caller_id = caller_id_for_scope(self._session, self._syntax, scope_stack)

        for child in node.children:
            prev = child.prev_sibling
            prev_type = prev.type if prev else None

            if ntype == "import_from_statement":
                if prev_type == "from":
                    text = self._resolve_import_text(child)
                    if text:
                        module.append(text)
                    continue
                if child.type == "wildcard_import":
                    continue
                self._collect_import_name(child, imported)

            elif ntype == "import_statement":
                if prev_type == "import" or prev_type == ",":
                    self._collect_bare_import(child, module, imported)

            elif ntype == "future_import_statement":
                if prev_type == "from":
                    module.append(self._syntax.node_text(child).strip())
                    continue
                self._collect_import_name(child, imported)

        if ntype != "import_statement":
            self._emit_from_import_edges(module, imported, ntype, caller_id)
        if ntype == "import_statement":
            self._emit_bare_import_edges(imported, caller_id)
        return None

    def _resolve_import_text(self, child: TSNode) -> str | None:
        text = self._syntax.node_text(child).strip()
        if text and text[0] == ".":
            return resolve_relative_import(self._session.module_id, text)
        return text or None

    def _collect_import_name(self, child: TSNode, names: list[tuple[str, str]]) -> None:
        ctype = child.type
        if ctype in ("dotted_name", "identifier"):
            name = self._syntax.node_text(child).strip()
            names.append((name, name))
        elif ctype == "aliased_import":
            original, alias = self._parse_aliased_import(child)
            if original:
                names.append((original, alias or original))

    def _collect_bare_import(
        self,
        child: TSNode,
        module: list[str],
        imported: list[tuple[str, str]],
    ) -> None:
        ctype = child.type
        if ctype == "dotted_name":
            text = self._resolve_import_text(child)
            if text:
                module.append(text)
                local = text.split(".")[0]
                imported.append((text, local))
        elif ctype == "aliased_import":
            original, alias = self._parse_aliased_import(child)
            if original:
                text = original
                if text and text[0] == ".":
                    text = (
                        resolve_relative_import(self._session.module_id, text) or text
                    )
                local = alias or text.split(".")[0]
                module.append(text)
                imported.append((text, local))

    def _parse_aliased_import(self, node: TSNode) -> tuple[str | None, str | None]:
        original: str | None = None
        alias: str | None = None
        for child in node.children:
            if child.type in ("dotted_name", "identifier"):
                if original is None:
                    original = self._syntax.node_text(child).strip()
                else:
                    alias = self._syntax.node_text(child).strip()
        return original, alias

    def _emit_from_import_edges(
        self,
        module: list[str],
        imported: list[tuple[str, str]],
        ntype: str,
        caller_id: str | None = None,
    ) -> None:
        if not module or not imported:
            return
        fc = self._session.file_ctx
        source = caller_id or self._session.module_id
        mod_name = module[0]
        for original, local in imported:
            qualified = f"{mod_name}::{original}"
            if ntype != "future_import_statement":
                fc.register_import(local, qualified)
            resolved_target = fc.resolve(local)
            edge_target = resolved_target if resolved_target else qualified
            append_import_edge(self._session, source, edge_target)

    def _emit_bare_import_edges(
        self,
        imported: list[tuple[str, str]],
        caller_id: str | None = None,
    ) -> None:
        fc = self._session.file_ctx
        source = caller_id or self._session.module_id
        for mod_text, local in imported:
            fc.register_import(local, mod_text)
            resolved_target = fc.resolve(local)
            edge_target = resolved_target if resolved_target else mod_text
            append_import_edge(self._session, source, edge_target)
