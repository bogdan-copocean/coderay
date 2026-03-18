"""Import handling: IMPORTS edges and FileContext registration."""

from __future__ import annotations

from typing import Any

from coderay.core.models import EdgeKind, GraphEdge
from coderay.graph._utils import resolve_relative_import

TSNode = Any


class ImportHandlerMixin:
    """Handle imports: IMPORTS edges and FileContext registration."""

    def _handle_import(self, node: TSNode) -> None:
        """Create IMPORTS edges and register names in FileContext."""
        ntype = node.type
        module: list[str] = []  # e.g. ["pathlib"] or ["collections"]
        imported: list[tuple[str, str]] = []  # (original, local) e.g. ("Path", "Path")

        # Walk AST children; prev_sibling tells us context
        for child in node.children:
            prev = child.prev_sibling
            prev_type = prev.type if prev else None

            if ntype == "import_from_statement":
                # "from X import Y" — child after "from" is the module
                if prev_type == "from":
                    text = self._resolve_import_text(child)
                    if text:
                        module.append(text)
                    continue
                # Child after "import" or "," is an imported name
                if child.type == "wildcard_import":
                    # from X import * — not resolved (known gap)
                    continue
                self._collect_import_name(child, imported)

            elif ntype == "import_statement":
                # "import X" or "import X as Y" — collect each module/alias
                if prev_type == "import" or prev_type == ",":
                    self._collect_bare_import(child, module, imported)

            elif ntype == "future_import_statement":
                if prev_type == "from":
                    module.append(self.node_text(child).strip())
                    continue
                self._collect_import_name(child, imported)

        # Emit IMPORTS edges for from-imports (skip excluded: typing, abc, etc.)
        if module and imported:
            mod_name = module[0]
            is_excluded = mod_name in self._excluded_modules
            for original, local in imported:
                qualified = f"{mod_name}::{original}"
                # Always register so Path(), dd() etc. resolve even from excluded mods
                if ntype != "future_import_statement":
                    self._file_ctx.register_import(local, qualified)
                if is_excluded:
                    continue  # No IMPORTS edge for typing, abc, __future__
                resolved_target = self._file_ctx.resolve(local)
                edge_target = resolved_target if resolved_target else qualified
                self._edges.append(
                    GraphEdge(
                        source=self._module_id,
                        target=edge_target,
                        kind=EdgeKind.IMPORTS,
                    )
                )

        # Bare imports: "import os" / "import os as my_os" — one edge per module
        if ntype == "import_statement":
            for mod_text, local in imported:
                self._file_ctx.register_import(local, mod_text)
                if mod_text in self._excluded_modules:
                    continue
                resolved_target = self._file_ctx.resolve(local)
                edge_target = resolved_target if resolved_target else mod_text
                self._edges.append(
                    GraphEdge(
                        source=self._module_id,
                        target=edge_target,
                        kind=EdgeKind.IMPORTS,
                    )
                )

    def _resolve_import_text(self, child: TSNode) -> str | None:
        """Resolve import module text; handle relative paths."""
        text = self.node_text(child).strip()
        # ".foo" or "..bar" → convert to slash path for module index lookup
        if text and text[0] == ".":
            return resolve_relative_import(self._module_id, text)
        return text or None

    def _collect_import_name(self, child: TSNode, names: list[tuple[str, str]]) -> None:
        """Collect imported name (Y or Y as Z) into names."""
        ctype = child.type
        # dotted_name/identifier = bare name; aliased_import = "X as Y"
        if ctype in ("dotted_name", "identifier"):
            name = self.node_text(child).strip()
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
        """Collect bare-import target (X or X as Y) into imported."""
        ctype = child.type
        # dotted_name = "os" or "collections.defaultdict"; aliased_import = "math as m"
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
                    text = resolve_relative_import(self._module_id, text) or text
                local = alias or text.split(".")[0]
                module.append(text)
                imported.append((text, local))

    def _parse_aliased_import(self, node: TSNode) -> tuple[str | None, str | None]:
        """Extract (original_name, alias) from aliased_import node."""
        original: str | None = None
        alias: str | None = None
        for child in node.children:
            if child.type in ("dotted_name", "identifier"):
                if original is None:
                    original = self.node_text(child).strip()
                else:
                    alias = self.node_text(child).strip()
        return original, alias
