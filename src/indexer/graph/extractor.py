"""Extract graph nodes and edges from tree-sitter ASTs.

Visits the already-parsed AST to produce:
  - MODULE nodes (one per file)
  - FUNCTION / CLASS nodes (definitions)
  - IMPORTS edges (module -> module)
  - DEFINES edges (module -> symbol)
  - CALLS edges (function -> function, best-effort static analysis)
  - INHERITS edges (class -> base class)

Supports Python, TypeScript/JavaScript, and Go via the language registry.
"""

from __future__ import annotations

import logging

from indexer.chunking.registry import get_language_for_file
from indexer.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind

logger = logging.getLogger(__name__)

# Method/function names that are Python/JS/Go built-ins or ubiquitous stdlib.
# Tracking these as CALLS edges adds noise without useful signal: they can
# never resolve to a project-internal node and inflate edge counts 3-5x.
BUILTIN_CALLEES: frozenset[str] = frozenset(
    {
        # Python built-in functions
        "abs", "all", "any", "ascii", "bin", "bool", "breakpoint",
        "bytearray", "bytes", "callable", "chr", "classmethod",
        "compile", "complex", "delattr", "dict", "dir", "divmod",
        "enumerate", "eval", "exec", "filter", "float", "format",
        "frozenset", "getattr", "globals", "hasattr", "hash", "hex",
        "id", "input", "int", "isinstance", "issubclass", "iter",
        "len", "list", "locals", "map", "max", "min", "next",
        "object", "oct", "open", "ord", "pow", "print", "property",
        "range", "repr", "reversed", "round", "set", "setattr",
        "slice", "sorted", "staticmethod", "str", "sum", "super",
        "tuple", "type", "vars", "zip",
        # Common str / bytes / list / dict / set methods
        "append", "extend", "insert", "remove", "pop", "clear",
        "copy", "count", "index", "reverse", "sort",
        "get", "keys", "values", "items", "update", "setdefault",
        "add", "discard", "union", "intersection", "difference",
        "encode", "decode", "strip", "lstrip", "rstrip",
        "split", "rsplit", "join", "replace", "find", "rfind",
        "startswith", "endswith", "upper", "lower", "title", "capitalize",
        "format", "format_map",
        "read", "write", "close", "flush", "seek", "tell",
        "read_text", "write_text", "read_bytes", "write_bytes",
        # Common logging / path / os helpers
        "debug", "info", "warning", "error", "critical", "exception",
        "getLogger", "basicConfig", "setLevel",
        "exists", "is_file", "is_dir", "mkdir", "rmdir", "unlink",
        "resolve", "absolute", "relative_to", "iterdir", "glob",
        "isatty", "hexdigest", "perf_counter", "time", "sleep",
        "dumps", "loads", "safe_load",
        "wraps",
        # Common JS/TS
        "log", "warn", "then", "catch", "finally", "map", "filter",
        "reduce", "forEach", "push", "splice", "slice", "concat",
        "toString", "valueOf", "keys", "values", "entries",
        "addEventListener", "removeEventListener",
        "querySelector", "querySelectorAll",
        "JSON", "parse", "stringify",
        # Common Go
        "Println", "Printf", "Sprintf", "Errorf", "Fatal", "Fatalf",
        "New", "Error",
        # Common testing
        "assertEqual", "assertTrue", "assertFalse", "assertRaises",
        "assertIn", "assertNotIn", "assertIsNone", "assertIsNotNone",
        "assert_called_once", "assert_called_once_with",
        "assert_not_called",
    }
)


def _extract_callee_name(text: str) -> str:
    """Extract the final method/function name from a call expression.

    'self._store.delete_by_paths' -> 'delete_by_paths'
    'logger.warning'              -> 'warning'
    'foo'                         -> 'foo'
    'a.b.c'                       -> 'c'
    """
    cleaned = text
    if cleaned.startswith("self."):
        cleaned = cleaned[5:]
    elif cleaned.startswith("this."):
        cleaned = cleaned[5:]
    parts = cleaned.split(".")
    return parts[-1] if parts else cleaned


class GraphExtractor:
    """Extract graph nodes and edges from source files."""

    def extract_from_file(
        self,
        file_path: str,
        content: str,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Parse a source file and extract all graph nodes and edges."""
        lang_cfg = get_language_for_file(file_path)
        if lang_cfg is None:
            return [], []

        try:
            parser = lang_cfg.get_parser()
        except Exception:
            return [], []

        source_bytes = content.encode("utf-8")
        tree = parser.parse(source_bytes)

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        module_id = file_path
        module_node = GraphNode(
            id=module_id,
            kind=NodeKind.MODULE,
            file_path=file_path,
            start_line=1,
            end_line=tree.root_node.end_point[0] + 1,
            name=file_path,
            qualified_name=file_path,
        )
        nodes.append(module_node)

        self._visit(
            tree.root_node,
            source_bytes,
            file_path,
            module_id,
            lang_cfg,
            scope_stack=[],
            nodes=nodes,
            edges=edges,
        )
        return nodes, edges

    def _visit(
        self,
        node,
        source_bytes,
        file_path,
        module_id,
        lang_cfg,
        scope_stack,
        nodes,
        edges,
    ):
        ntype = node.type

        if ntype in lang_cfg.import_types:
            self._handle_import(node, source_bytes, module_id, edges)
        elif ntype in lang_cfg.scope_types and "function" in ntype:
            self._handle_function_def(
                node,
                source_bytes,
                file_path,
                module_id,
                lang_cfg,
                scope_stack,
                nodes,
                edges,
            )
            return
        elif ntype in lang_cfg.scope_types and "class" in ntype:
            self._handle_class_def(
                node,
                source_bytes,
                file_path,
                module_id,
                lang_cfg,
                scope_stack,
                nodes,
                edges,
            )
            return
        elif ntype in lang_cfg.scope_types and "method" in ntype:
            self._handle_function_def(
                node,
                source_bytes,
                file_path,
                module_id,
                lang_cfg,
                scope_stack,
                nodes,
                edges,
            )
            return
        elif ntype in lang_cfg.scope_types and "interface" in ntype:
            self._handle_class_def(
                node,
                source_bytes,
                file_path,
                module_id,
                lang_cfg,
                scope_stack,
                nodes,
                edges,
            )
            return
        elif ntype == "call" or ntype == "call_expression":
            self._handle_call(
                node, source_bytes, file_path, module_id, scope_stack, edges
            )

        for child in node.children:
            self._visit(
                child,
                source_bytes,
                file_path,
                module_id,
                lang_cfg,
                scope_stack,
                nodes,
                edges,
            )

    def _handle_import(self, node, source_bytes, module_id, edges):
        for child in node.children:
            if child.type in ("dotted_name", "relative_import"):
                target = self._node_text(child, source_bytes)
                edges.append(
                    GraphEdge(
                        source=module_id,
                        target=target,
                        kind=EdgeKind.IMPORTS,
                    )
                )
            elif child.type == "string":
                target = self._node_text(child, source_bytes).strip("'\"")
                if target:
                    edges.append(
                        GraphEdge(
                            source=module_id,
                            target=target,
                            kind=EdgeKind.IMPORTS,
                        )
                    )
            elif child.type == "interpreted_string_literal":
                target = self._node_text(child, source_bytes).strip('"')
                if target:
                    edges.append(
                        GraphEdge(
                            source=module_id,
                            target=target,
                            kind=EdgeKind.IMPORTS,
                        )
                    )

    def _handle_function_def(
        self,
        node,
        source_bytes,
        file_path,
        module_id,
        lang_cfg,
        scope_stack,
        nodes,
        edges,
    ):
        name = self._get_identifier(node, source_bytes)
        if not name:
            return
        qualified = ".".join([*scope_stack, name])
        node_id = f"{file_path}::{qualified}"
        nodes.append(
            GraphNode(
                id=node_id,
                kind=NodeKind.FUNCTION,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                name=name,
                qualified_name=qualified,
            )
        )
        edges.append(
            GraphEdge(
                source=module_id,
                target=node_id,
                kind=EdgeKind.DEFINES,
            )
        )
        new_scope = [*scope_stack, name]
        for child in node.children:
            self._visit(
                child,
                source_bytes,
                file_path,
                module_id,
                lang_cfg,
                new_scope,
                nodes,
                edges,
            )

    def _handle_class_def(
        self,
        node,
        source_bytes,
        file_path,
        module_id,
        lang_cfg,
        scope_stack,
        nodes,
        edges,
    ):
        name = self._get_identifier(node, source_bytes)
        if not name:
            return
        qualified = ".".join([*scope_stack, name])
        node_id = f"{file_path}::{qualified}"
        nodes.append(
            GraphNode(
                id=node_id,
                kind=NodeKind.CLASS,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                name=name,
                qualified_name=qualified,
            )
        )
        edges.append(
            GraphEdge(
                source=module_id,
                target=node_id,
                kind=EdgeKind.DEFINES,
            )
        )
        for child in node.children:
            if child.type in ("argument_list", "superclass", "extends_clause"):
                for arg in child.children:
                    if arg.type in (
                        "identifier",
                        "dotted_name",
                        "attribute",
                        "type_identifier",
                    ):
                        base_name = self._node_text(arg, source_bytes)
                        if base_name:
                            edges.append(
                                GraphEdge(
                                    source=node_id,
                                    target=base_name,
                                    kind=EdgeKind.INHERITS,
                                )
                            )
        new_scope = [*scope_stack, name]
        for child in node.children:
            self._visit(
                child,
                source_bytes,
                file_path,
                module_id,
                lang_cfg,
                new_scope,
                nodes,
                edges,
            )

    def _handle_call(
        self, node, source_bytes, file_path, module_id, scope_stack, edges
    ):
        caller_id = (
            f"{file_path}::{'.'.join(scope_stack)}" if scope_stack else module_id
        )
        first_child = node.children[0] if node.children else None
        if first_child is None:
            return
        raw_callee = self._node_text(first_child, source_bytes)
        if not raw_callee:
            return
        callee_name = _extract_callee_name(raw_callee)
        if callee_name and callee_name not in BUILTIN_CALLEES:
            edges.append(
                GraphEdge(
                    source=caller_id,
                    target=callee_name,
                    kind=EdgeKind.CALLS,
                )
            )

    @staticmethod
    def _get_identifier(node, source_bytes):
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "field_identifier"):
                return source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="replace"
                )
        return ""

    @staticmethod
    def _node_text(node, source_bytes):
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )
