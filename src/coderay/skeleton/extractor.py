from __future__ import annotations

import logging
from pathlib import Path

from coderay.parsing.base import BaseTreeSitterParser, TSNode, get_parse_context

logger = logging.getLogger(__name__)

ELLIPSIS = "..."


def _inclusive_rows_1based(node) -> tuple[int, int]:
    """Return 1-based inclusive start/end line for node (matches chunker convention)."""
    # Tree-sitter rows are 0-based; path suffix `path:START-END` is 1-based for humans.
    return node.start_point[0] + 1, node.end_point[0] + 1


def extract_skeleton(
    path: str | Path,
    content: str,
    *,
    include_imports: bool = False,
    symbol: str | None = None,
    line_range: tuple[int, int] | None = None,
) -> str:
    """Extract skeleton (signatures, no bodies).

    Each symbol is preceded by absolute path and symbol line range. Optional
    file line range keeps only declarations fully within that window.
    """
    if line_range is not None:
        lo, hi = line_range
        if lo < 1 or hi < 1 or hi < lo:
            raise ValueError("line_range must be 1-based inclusive with end >= start")

    ctx = get_parse_context(path, content)
    if ctx is None:
        return content

    parser = SkeletonTreeSitterParser(
        ctx,
        include_imports=include_imports,
        symbol=symbol,
        line_range=line_range,
    )
    try:
        lines = parser.collect_lines()
    except Exception:  # pragma: no cover - defensive fallback
        logger.exception("Skeleton extraction failed")
        return content

    if not lines:
        if line_range is not None:
            a, b = line_range
            return f"# No skeleton entries in file line range {a}-{b}."
        if symbol:
            return _symbol_not_found_hint(ctx, symbol)
    return "\n".join(lines)


def _symbol_not_found_hint(ctx, symbol: str) -> str:
    """Return a diagnostic listing the top-level symbols in *ctx*."""
    lang_cfg = ctx.lang_cfg
    helper = BaseTreeSitterParser(ctx)
    tree = helper.get_tree()
    names: list[str] = []
    for child in tree.root_node.children:
        node = child
        if node.type in lang_cfg.cst.decorator_scope_types:
            for inner in node.named_children:
                if inner.type in (
                    *lang_cfg.cst.function_scope_types,
                    *lang_cfg.cst.class_scope_types,
                ):
                    node = inner
                    break
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            raw = name_node.text
            if raw is not None:
                names.append(raw.decode() if isinstance(raw, bytes) else raw)
    available = ", ".join(sorted(set(names))) if names else "(none)"
    return f"# Symbol '{symbol}' not found. Available symbols: {available}"


class SkeletonTreeSitterParser(BaseTreeSitterParser):
    """Tree-sitter skeleton parser."""

    def __init__(
        self,
        context,
        *,
        include_imports: bool = True,
        symbol: str | None = None,
        line_range: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(context)
        self._include_imports = include_imports
        self._symbol = symbol
        # Optional --lines / path:START-END filter. Stored 0-based inclusive to match
        # tree-sitter start_point/end_point rows (CLI input is 1-based).
        self._file_line_range0: tuple[int, int] | None = None
        if line_range is not None:
            a, b = line_range
            self._file_line_range0 = (a - 1, b - 1)
        self._root_node: TSNode | None = None
        self._abs_display = str(Path(self._ctx.file_path).resolve())
        # Some (e.g. decorated) defs already printed path:range;
        # skip duplicate on inner _dfs.
        self._omit_next_skeleton_path_line = False

    def _rows_vs_line_filter(self, ns: int, ne: int, *, contained: bool) -> bool:
        """Return whether [ns,ne] overlaps or is contained in the file line filter."""
        # ns, ne and filter bounds: 0-based inclusive rows (tree-sitter).
        if self._file_line_range0 is None:
            return True
        lo, hi = self._file_line_range0
        if contained:
            return ns >= lo and ne <= hi
        return not (ne < lo or ns > hi)

    def _node_overlaps_line_filter(self, node) -> bool:
        """Return True if node overlaps the file line range (0-based rows)."""
        ns, ne = node.start_point[0], node.end_point[0]
        return self._rows_vs_line_filter(ns, ne, contained=False)

    def _node_fully_in_line_filter(self, node) -> bool:
        """Return True if node span lies entirely in the file line range."""
        ns, ne = node.start_point[0], node.end_point[0]
        return self._rows_vs_line_filter(ns, ne, contained=True)

    def collect_lines(self) -> list[str]:
        """Return skeleton lines."""
        tree = self.get_tree()
        self._root_node = tree.root_node
        lines: list[str] = []
        self._seen: set[int] = set()
        self._dfs(tree.root_node, lines, depth=0)
        return lines

    def _emit_path_header(self, lines: list[str], decl_node) -> None:
        """Emit one line: absolute path and symbol line range suffix."""
        lo, hi = _inclusive_rows_1based(decl_node)
        lines.append(f"{self._abs_display}:{lo}-{hi}")

    def _emit_first(self, lines: list[str], decl_node, indent: str, text: str) -> None:
        """Emit path header then first line of a symbol block."""
        if self._omit_next_skeleton_path_line:
            self._omit_next_skeleton_path_line = False
        else:
            self._emit_path_header(lines, decl_node)
        lines.append(indent + text)

    def _emit_cont(self, lines: list[str], indent: str, text: str) -> None:
        """Emit continuation line (no symbol line range column)."""
        lines.append(indent + text)

    def _extract_text(self, node) -> str | None:
        """Extract string from docstring-capable node (e.g. expression_statement)."""
        expr_type = self._ctx.lang_cfg.skeleton.docstring_expr_type
        if node.type != expr_type:
            return None
        for sub in node.children:
            if sub.type == "string":
                return self.node_text(sub).strip()
        return None

    def _get_docstring(self, node) -> str | None:
        """Extract docstring from body block."""
        if not hasattr(node, "children"):
            return None

        lang_cfg = self._ctx.lang_cfg
        scope_types = (
            *lang_cfg.cst.function_scope_types,
            *lang_cfg.cst.class_scope_types,
        )
        if node.type in scope_types:
            body_block_types = lang_cfg.skeleton.body_block_types
            body = None
            for child in node.children:
                if child.type in body_block_types:
                    body = child
                    break

            if body is None:
                return None

            for child in body.children:
                if text := self._extract_text(child):
                    return text

        for child in node.children:
            if text := self._extract_text(child):
                return text
        return None

    def _get_signature_line(self, node) -> str:
        """Return text up to colon or brace."""
        text = self.node_text(node)
        for delimiter in (":\n", "{\n", ":\r\n", "{\r\n"):
            idx = text.find(delimiter)
            if idx >= 0:
                return text[: idx + 1]
        first_line = text.split("\n")[0]
        return first_line

    def _emit_signature_block(
        self,
        lines: list[str],
        node,
        indent: str,
        *,
        ellipsis: bool,
    ) -> None:
        """Emit signature line, optional docstring, optional body ellipsis."""
        self._emit_first(lines, node, indent, self._get_signature_line(node))
        if docstr := self._get_docstring(node):
            self._emit_cont(lines, indent, "    " + docstr)
        if ellipsis:
            self._emit_cont(lines, indent, "    " + ELLIPSIS)

    def _node_name(self, node) -> str | None:
        """Extract declared name from node."""
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return self.node_text(name_node).strip()
        return None

    def _matches_symbol(self, node, depth: int) -> bool:
        """Return True if node is on the symbol path at this depth.

        One dotted segment is consumed per depth level: "a.b.c" matches
        "a" at depth=0, "b" at depth=1, "c" at depth=2. Once the path is
        exhausted (depth >= len(parts)) all children are allowed through so
        the target's body is still traversed.
        """
        if self._symbol is None:
            return True
        parts = self._symbol.split(".")
        if depth >= len(parts):
            return True
        return self._node_name(node) == parts[depth]

    def _is_symbol_target(self, node, depth: int) -> bool:
        """Return True if this node should emit its signature.

        At the terminal segment always emit. For intermediate nodes, emit
        class headers (useful context for Class.method) but suppress
        function headers (closure wrappers add no value when targeting inner).
        """
        if self._symbol is None:
            return True
        parts = self._symbol.split(".")
        if depth >= len(parts) - 1:
            return True
        lang_cfg = self._ctx.lang_cfg
        return node.type in lang_cfg.cst.class_scope_types

    def _would_emit_decl(self, node, depth: int) -> bool:
        """Return True if this node should emit (symbol filter + line window)."""
        return self._is_symbol_target(node, depth) and self._node_fully_in_line_filter(
            node
        )

    def _is_call_argument(self, node) -> bool:
        """Return True if *node* is an argument to a call expression.

        Arrow functions appearing directly inside an ``arguments`` node are
        callback arguments (implementation detail) and should not be emitted
        as skeleton entries.
        """
        parent = node.parent
        return parent is not None and parent.type == "arguments"

    def _decorated_inner(self, node):
        """Return inner class/function from decorated node."""
        lang_cfg = self._ctx.lang_cfg
        for child in node.named_children:
            if child.type in (
                *lang_cfg.cst.function_scope_types,
                *lang_cfg.cst.class_scope_types,
            ):
                return child
        return None

    def _dfs(self, node, lines: list[str], depth: int) -> None:

        if node.id in self._seen:
            return

        if (
            self._file_line_range0 is not None
            and node is not self._root_node
            and not self._node_overlaps_line_filter(node)
        ):
            return

        indent = "    " * depth
        ntype = node.type
        lang_cfg = self._ctx.lang_cfg
        skel = lang_cfg.skeleton
        cst = lang_cfg.cst

        if ntype in cst.import_types:
            if (
                self._include_imports
                and self._symbol is None
                and self._node_fully_in_line_filter(node)
            ):
                self._emit_first(lines, node, indent, self.node_text(node).strip())
            return

        if ntype in skel.symbol_types:
            if ntype in cst.decorator_scope_types:
                self._dfs_decorated(node, lines, depth, indent, lang_cfg)
                return
            if ntype in cst.function_scope_types:
                self._dfs_function(node, lines, depth, indent, ntype)
                return
            if ntype in cst.class_scope_types:
                self._dfs_class(node, lines, depth, indent)
                return
            self._seen.add(node.id)
            for child in node.children:
                self._dfs(child, lines, depth)
            return

        if depth == 0 and ntype in skel.top_level_expr_types and self._symbol is None:
            text = self.node_text(node).strip()
            if (
                text
                and (text.startswith(('"""', "'''", '"', "'")) or "=" in text)
                and self._node_fully_in_line_filter(node)
            ):
                self._emit_first(lines, node, "", text)
            for child in node.children:
                self._dfs(child, lines, depth)
            return

        self._seen.add(node.id)
        for child in node.children:
            self._dfs(child, lines, depth)

    def _dfs_decorated(
        self, node, lines: list[str], depth: int, indent: str, lang_cfg
    ) -> None:
        """Path line, decorator lines, then inner (skip duplicate path)."""
        inner = self._decorated_inner(node)
        if inner is not None and not self._matches_symbol(inner, depth):
            self._seen.add(node.id)
            return
        if inner is not None and self._would_emit_decl(inner, depth):
            self._emit_path_header(lines, inner)
        for child in node.named_children:
            if child.type == "decorator":
                if (
                    inner is not None
                    and self._is_symbol_target(inner, depth)
                    and self._node_fully_in_line_filter(child)
                ):
                    self._emit_cont(lines, indent, self.node_text(child).strip())
                self._seen.add(child.id)
                continue
            if child.type in (
                *lang_cfg.cst.function_scope_types,
                *lang_cfg.cst.class_scope_types,
            ):
                if inner is not None and self._would_emit_decl(inner, depth):
                    # Path line already emitted; next emit_first skips path:range.
                    self._omit_next_skeleton_path_line = True
                self._dfs(child, lines, depth)
                break
        self._seen.add(node.id)

    def _dfs_function(
        self, node, lines: list[str], depth: int, indent: str, ntype: str
    ) -> None:
        """Signature + docstring + ellipsis; recurse into body."""
        if ntype == "arrow_function" and self._is_call_argument(node):
            self._seen.add(node.id)
            return
        if not self._matches_symbol(node, depth):
            self._seen.add(node.id)
            return
        if self._would_emit_decl(node, depth):
            self._emit_signature_block(lines, node, indent, ellipsis=True)
        self._seen.add(node.id)
        for child in node.children:
            self._dfs(child, lines, depth + 1)

    def _dfs_class(self, node, lines: list[str], depth: int, indent: str) -> None:
        """Class-like: signature + docstring; recurse into body."""
        if not self._matches_symbol(node, depth):
            self._seen.add(node.id)
            return
        if self._would_emit_decl(node, depth):
            self._emit_signature_block(lines, node, indent, ellipsis=False)
        self._seen.add(node.id)
        for child in node.children:
            self._dfs(child, lines, depth + 1)
