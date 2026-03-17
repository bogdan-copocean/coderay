"""Import handling for graph extraction.

Creates IMPORTS edges (module -> imported symbol) and registers each
imported name in FileContext so later calls like ``Path()`` or ``dd(int)``
resolve to the correct target. Tree-sitter uses prev_sibling to distinguish
module names from imported names (no positional field for "after import").
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coderay.core.models import EdgeKind, GraphEdge

if TYPE_CHECKING:
    from tree_sitter import Tree
from coderay.graph._utils import resolve_relative_import

TSNode = Any


class ImportHandlerMixin:
    """Handles import statements: IMPORTS edges and FileContext registration."""

    def _handle_import(self, node: TSNode) -> None:
        """Create IMPORTS edges and register names in FileContext.

        Handles bare imports, from-imports, aliased imports, future imports.
        Uses prev_sibling to identify module/names. Excluded modules are
        still registered (for resolution) but produce no IMPORTS edges.
        """
        ntype = node.type
        module: list[str] = []  # e.g. ["pathlib"] or ["collections"]
        imported: list[tuple[str, str]] = []  # (original, local) e.g. ("Path", "Path")

        # Walk AST children; prev_sibling tells us context (after "from", "import", etc.)
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
                    # from X import * — resolve via __all__ or public names
                    imported.extend(self._resolve_wildcard_exports(module))
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
        """Resolve the text of an import module node, handling relative paths."""
        text = self.node_text(child).strip()
        # ".foo" or "..bar" → convert to slash path for module index lookup
        if text and text[0] == ".":
            return resolve_relative_import(self._module_id, text)
        return text or None

    def _collect_import_name(
        self, child: TSNode, names: list[tuple[str, str]]
    ) -> None:
        """Collect an imported name (``Y`` or ``Y as Z``) into *names*."""
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
        """Collect a bare-import target (``X`` or ``X as Y``) into *imported*."""
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

    def _resolve_wildcard_exports(
        self, module: list[str]
    ) -> list[tuple[str, str]]:
        """Resolve names from ``from X import *`` via __all__ or public names."""
        if not module:
            return []
        mod_name = module[0]
        file_path = self._module_index.get(mod_name)
        if not file_path:
            return []
        content = self._content_provider.get(file_path)
        if not content:
            return []
        # Try to parse and find __all__ or public names
        try:
            from tree_sitter import Language, Parser

            from coderay.parsing.languages import get_language_for_file

            lang_cfg = get_language_for_file(file_path)
            if not lang_cfg or lang_cfg.name != "python":
                return []
            lang = Language(lang_cfg.language_fn())
            parser = Parser(lang)
            tree = parser.parse(content.encode())
            return self._extract_names_from_module(tree, content, mod_name)
        except Exception:
            return []

    def _extract_names_from_module(
        self, tree: Tree, content: str, mod_name: str
    ) -> list[tuple[str, str]]:
        """Extract __all__ or public names from a module's AST."""
        root = tree.root_node
        if not root:
            return []

        # Check for __all__
        for child in root.named_children:
            if child.type != "expression_statement":
                continue
            stmt = child.named_children[0] if child.named_children else None
            if not stmt or stmt.type != "assignment":
                continue
            lhs = stmt.child_by_field_name("left") or (
                stmt.named_children[0] if stmt.named_children else None
            )
            rhs = stmt.child_by_field_name("right") or (
                stmt.named_children[-1] if len(stmt.named_children) >= 2 else None
            )
            if not lhs or not rhs:
                continue
            if content[lhs.start_byte : lhs.end_byte] != "__all__":
                continue
            if rhs.type in ("list", "tuple", "expression_list"):
                names = []
                for c in rhs.named_children:
                    if c.type == "string":
                        s = content[c.start_byte : c.end_byte].strip('"\'')
                        if s and not s.startswith("_"):
                            names.append((s, s))
                    elif c.type == "identifier":
                        n = content[c.start_byte : c.end_byte]
                        if n and n != "_":
                            names.append((n, n))
                return names

        # Fallback: top-level def/class names
        result: list[tuple[str, str]] = []
        for child in root.named_children:
            if child.type in ("function_definition", "class_definition"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = content[name_node.start_byte : name_node.end_byte]
                    if name and not name.startswith("_"):
                        result.append((name, name))
        return result

    def _parse_aliased_import(
        self, node: TSNode
    ) -> tuple[str | None, str | None]:
        """Extract ``(original_name, alias)`` from an ``aliased_import`` node.

        AST: aliased_import has children [dotted_name, identifier] for "X as Y".
        """
        original: str | None = None
        alias: str | None = None
        for child in node.children:
            if child.type in ("dotted_name", "identifier"):
                if original is None:
                    original = self.node_text(child).strip()
                else:
                    alias = self.node_text(child).strip()
        return original, alias
