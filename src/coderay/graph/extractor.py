from __future__ import annotations

import builtins
import logging
from typing import Any

from coderay.chunking.registry import LanguageConfig, get_language_for_file
from coderay.core.config import get_config
from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.parsing.base import BaseTreeSitterParser, ParserContext

logger = logging.getLogger(__name__)

_PYTHON_BUILTINS: frozenset[str] = frozenset(
    name for name in dir(builtins) if not name.startswith("_")
)


def build_callee_filter() -> frozenset[str]:
    """Build the callee exclusion set from builtins + application config.

    Returns:
        Frozen set of callee names to exclude from CALLS edges.
    """
    config = get_config()
    graph_cfg = getattr(config, "graph", None) or {}
    if not isinstance(graph_cfg, dict):
        graph_cfg = {}
    extra_excludes = set(graph_cfg.get("exclude_callees") or [])
    force_includes = set(graph_cfg.get("include_callees") or [])
    return frozenset((_PYTHON_BUILTINS | extra_excludes) - force_includes)


def _resolve_relative_import(source_file: str, relative_target: str) -> str | None:
    """Resolve a Python relative import to a path-based target.

    Args:
        source_file: Path of the file containing the import.
        relative_target: Dotted import string starting with one or more dots.

    Returns:
        Slash-separated path (no extension), or None if dots exceed
        the directory depth.
    """
    dots = len(relative_target) - len(relative_target.lstrip("."))
    rest = relative_target[dots:]

    parts = source_file.replace("\\", "/").split("/")
    dir_parts = parts[:-1]

    levels_up = max(dots - 1, 0)
    if levels_up > len(dir_parts):
        return None
    if levels_up > 0:
        dir_parts = dir_parts[:-levels_up]

    if rest:
        dir_parts.extend(rest.split("."))

    return "/".join(dir_parts) if dir_parts else None


def _extract_callee_name(text: str) -> str:
    """Extract the final method/function name from a call expression."""
    cleaned = text
    if cleaned.startswith("self."):
        cleaned = cleaned[5:]
    elif cleaned.startswith("this."):
        cleaned = cleaned[5:]
    parts = cleaned.split(".")
    return parts[-1] if parts else cleaned


class GraphExtractor(BaseTreeSitterParser):
    """Extract graph nodes and edges from source files."""

    def __init__(self) -> None:
        """Initialize the extractor from the application config."""
        dummy_ctx = ParserContext(file_path="", content="", lang_cfg=None)
        super().__init__(dummy_ctx)
        self._excluded_callees = build_callee_filter()
        self._module_id: str = ""
        self._lang_cfg: LanguageConfig | None = None
        self._nodes: list[GraphNode] = []
        self._edges: list[GraphEdge] = []

    def extract_from_file(
        self,
        file_path: str,
        content: str,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Parse a source file and extract all graph nodes and edges.

        Returns:
            Tuple of (nodes, edges). Returns ``([], [])`` if the language
            is unsupported or parsing fails.
        """
        lang_cfg = get_language_for_file(file_path)
        if lang_cfg is None:
            return [], []

        context = ParserContext(file_path=file_path, content=content, lang_cfg=lang_cfg)
        # Reinitialize the base parser with the real context for this file.
        self.__init__()
        self._ctx = context
        self._source_bytes = context.content.encode("utf-8")
        self._module_id = file_path
        self._lang_cfg = lang_cfg
        self._nodes = []
        self._edges = []

        try:
            tree = self.get_tree()
        except Exception:
            return [], []

        module_node = GraphNode(
            id=self._module_id,
            kind=NodeKind.MODULE,
            file_path=file_path,
            start_line=1,
            end_line=tree.root_node.end_point[0] + 1,
            name=file_path,
            qualified_name=file_path,
        )
        self._nodes.append(module_node)

        self._visit(tree.root_node, scope_stack=[])
        return self._nodes, self._edges

    # ------------------------------------------------------------------
    # Tree traversal
    # ------------------------------------------------------------------

    def _visit(self, node, *, scope_stack: list[str]) -> None:
        """Recursively walk the syntax tree, dispatching to type-specific handlers."""
        ntype = node.type
        lang_cfg = self._lang_cfg

        if ntype in lang_cfg.import_types:
            self._handle_import(node)
        elif ntype in lang_cfg.function_scope_types:
            self._handle_function_def(node, scope_stack=scope_stack)
            return
        elif ntype in lang_cfg.class_scope_types:
            self._handle_class_def(node, scope_stack=scope_stack)
            return
        elif ntype in lang_cfg.call_types:
            self._handle_call(node, scope_stack=scope_stack)

        for child in node.children:
            self._visit(child, scope_stack=scope_stack)

    # ------------------------------------------------------------------
    # Node-type handlers
    # ------------------------------------------------------------------

    def _handle_import(self, node) -> None:
        """Create IMPORTS edges for an import statement."""
        is_from_import = node.type == "import_from_statement"
        found_module = False
        for child in node.children:
            if child.type in ("dotted_name", "relative_import"):
                if is_from_import and found_module:
                    continue
                target = self._text(child)
                if target:
                    if child.type == "relative_import" and target.startswith("."):
                        resolved = _resolve_relative_import(self._module_id, target)
                        if resolved:
                            target = resolved
                    self._edges.append(
                        GraphEdge(
                            source=self._module_id,
                            target=target,
                            kind=EdgeKind.IMPORTS,
                        )
                    )
                    if is_from_import:
                        found_module = True
            elif child.type == "string":
                target = self._text(child).strip("'\"")
                if target:
                    self._edges.append(
                        GraphEdge(
                            source=self._module_id,
                            target=target,
                            kind=EdgeKind.IMPORTS,
                        )
                    )
            elif child.type == "interpreted_string_literal":
                target = self._text(child).strip('"')
                if target:
                    self._edges.append(
                        GraphEdge(
                            source=self._module_id,
                            target=target,
                            kind=EdgeKind.IMPORTS,
                        )
                    )

    def _handle_function_def(self, node, *, scope_stack: list[str]) -> None:
        """Create a FUNCTION node and DEFINES edge, then recurse into the body."""
        name = self._get_identifier(node)
        if not name:
            return
        qualified = ".".join([*scope_stack, name])
        node_id = f"{self._file_path}::{qualified}"
        self._nodes.append(
            GraphNode(
                id=node_id,
                kind=NodeKind.FUNCTION,
                file_path=self._file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                name=name,
                qualified_name=qualified,
            )
        )
        self._edges.append(
            GraphEdge(
                source=self._module_id,
                target=node_id,
                kind=EdgeKind.DEFINES,
            )
        )
        new_scope = [*scope_stack, name]
        for child in node.children:
            self._visit(child, scope_stack=new_scope)

    def _handle_class_def(self, node, *, scope_stack: list[str]) -> None:
        """Create a CLASS node, DEFINES + INHERITS edges, then recurse."""
        name = self._get_identifier(node)
        if not name:
            return
        qualified = ".".join([*scope_stack, name])
        node_id = f"{self._file_path}::{qualified}"
        self._nodes.append(
            GraphNode(
                id=node_id,
                kind=NodeKind.CLASS,
                file_path=self._file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                name=name,
                qualified_name=qualified,
            )
        )
        self._edges.append(
            GraphEdge(
                source=self._module_id,
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
                        if base_name := self._text(arg):
                            self._edges.append(
                                GraphEdge(
                                    source=node_id,
                                    target=base_name,
                                    kind=EdgeKind.INHERITS,
                                )
                            )
        new_scope = [*scope_stack, name]
        for child in node.children:
            self._visit(child, scope_stack=new_scope)

    def _handle_call(self, node, *, scope_stack: list[str]) -> None:
        """Create a CALLS edge from the enclosing scope to the callee."""
        caller_id = (
            f"{self._file_path}::{'.'.join(scope_stack)}"
            if scope_stack
            else self._module_id
        )
        first_child = node.children[0] if node.children else None
        if first_child is None:
            return
        raw_callee = self._text(first_child)
        if not raw_callee:
            return
        callee_name = _extract_callee_name(raw_callee)
        if callee_name and callee_name not in self._excluded_callees:
            self._edges.append(
                GraphEdge(
                    source=caller_id,
                    target=callee_name,
                    kind=EdgeKind.CALLS,
                )
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_identifier(self, node) -> str:
        """Return the identifier name from a definition node."""
        return self.identifier_from_node(node)

    def _text(self, node) -> str:
        """Decode the raw source text spanned by a syntax tree node."""
        return self.node_text(node)
