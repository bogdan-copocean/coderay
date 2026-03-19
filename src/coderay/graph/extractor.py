"""Extract code graph (nodes, edges) from source via tree-sitter."""

from __future__ import annotations

import logging
from typing import Any

from coderay.core.config import get_config
from coderay.core.models import GraphEdge, GraphNode, NodeKind
from coderay.graph._handlers import (
    AssignmentHandlerMixin,
    CallHandlerMixin,
    DefinitionHandlerMixin,
    ImportHandlerMixin,
    TypeResolutionMixin,
)
from coderay.graph._utils import is_init_file, resolve_relative_import
from coderay.graph.identifiers import file_path_to_module_names
from coderay.graph.lang_constants import (
    _PYTHON_BUILTINS,
    LangConstants,
    get_lang_constants,
)
from coderay.parsing.base import BaseTreeSitterParser, ParserContext, parse_file

# Re-export for tests that assert on internal helpers
_resolve_relative_import = resolve_relative_import

__all__ = [
    "FileContext",
    "GraphTreeSitterParser",
    "ModuleIndex",
    "_PYTHON_BUILTINS",
    "_resolve_relative_import",
    "build_module_filter",
    "build_module_index",
    "extract_graph_from_file",
]

logger = logging.getLogger(__name__)

TSNode = Any

_DEFAULT_EXCLUDED_MODULES: frozenset[str] = frozenset(
    {
        "builtins",
        "typing",
        "typing_extensions",
        "abc",
        "__future__",
    }
)

ModuleIndex = dict[str, str]


def build_module_index(file_paths: list[str]) -> ModuleIndex:
    """Build module index mapping dotted module names to file paths."""
    module_index: ModuleIndex = {}
    for fp in file_paths:
        for mod_name in file_path_to_module_names(fp):
            if mod_name not in module_index:
                module_index[mod_name] = fp
    return module_index


class FileContext:
    """Track name bindings for imports, definitions, instances, aliases."""

    def __init__(self, module_index: ModuleIndex | None = None) -> None:
        self._symbols: dict[str, str] = {}
        self._instances: dict[str, str] = {}
        self._instance_unions: dict[str, list[str]] = {}
        self._class_attributes: dict[str, str] = {}
        self._classes: set[str] = set()
        self._module_index = module_index or {}

    def _resolve_module_to_file(self, mod_name: str) -> str | None:
        """Resolve dotted module name to file path."""
        return self._module_index.get(mod_name)

    def _resolve_qualified_import(self, mod_name: str, symbol: str) -> str:
        """Resolve from-module import to file-path-based target."""
        submod = f"{mod_name}.{symbol}"
        submod_file = self._resolve_module_to_file(submod)
        if submod_file:
            return submod_file

        file_path = self._resolve_module_to_file(mod_name)
        if not file_path:
            return f"{mod_name}::{symbol}"

        if is_init_file(file_path):
            return f"{mod_name}::{symbol}"

        return f"{file_path}::{symbol}"

    def register_import(self, local_name: str, qualified_name: str) -> None:
        """Register an imported symbol binding."""
        if "::" in qualified_name:
            mod_part, sym_part = qualified_name.split("::", 1)
            resolved = self._resolve_qualified_import(mod_part, sym_part)
            self._symbols[local_name] = resolved
        else:
            file_path = self._resolve_module_to_file(qualified_name)
            self._symbols[local_name] = file_path if file_path else qualified_name

    def register_definition(
        self, local_name: str, node_id: str, *, is_class: bool = False
    ) -> None:
        """Register a locally defined class or function."""
        self._symbols[local_name] = node_id
        if is_class:
            self._classes.add(local_name)

    def register_instance(self, var_name: str, class_ref: str) -> None:
        """Register a variable as an instance of a class."""
        self._instances[var_name] = class_ref
        self._instance_unions.pop(var_name, None)

    def register_instance_union(self, var_name: str, class_refs: list[str]) -> None:
        """Register a variable as an instance of a union of classes."""
        if not class_refs:
            return
        self._instance_unions[var_name] = class_refs
        self._instances.pop(var_name, None)

    def register_class_attribute(
        self, class_qualified: str, attr_name: str, type_ref: str
    ) -> None:
        """Register a class attribute's type for method resolution."""
        self._class_attributes[f"{class_qualified}.{attr_name}"] = type_ref

    def resolve_class_attribute(
        self, class_qualified: str, attr_name: str
    ) -> str | None:
        """Look up a class attribute's type (e.g. from @property return type)."""
        return self._class_attributes.get(f"{class_qualified}.{attr_name}")

    def register_alias(self, alias_name: str, qualified_name: str) -> None:
        """Register a name alias pointing to an already-qualified target."""
        self._symbols[alias_name] = qualified_name

    def resolve(self, name: str) -> str | None:
        """Look up a name in the unified symbol table."""
        return self._symbols.get(name)

    def resolve_instance(self, var_name: str) -> str | None:
        """Look up a variable's originating class reference."""
        return self._instances.get(var_name)

    def resolve_method_call(self, obj_name: str, method_name: str) -> str | None:
        """Resolve obj.method() for tracked instance; first match for unions."""
        targets = self.resolve_method_calls(obj_name, method_name)
        return targets[0] if targets else None

    def resolve_method_calls(self, obj_name: str, method_name: str) -> list[str]:
        """Resolve obj.method() to all targets (handles unions)."""
        union_refs = self._instance_unions.get(obj_name)
        if union_refs:
            return [f"{ref}.{method_name}" for ref in union_refs]
        class_ref = self._instances.get(obj_name)
        if class_ref is None:
            return []
        return [f"{class_ref}.{method_name}"]

    def resolve_chain(self, chain: str) -> list[str]:
        """Resolve obj.attr1.attr2 to class refs for the final attribute.

        For service.client.get, chain is "service.client", returns [HttpClient].
        """
        parts = chain.split(".")
        if not parts:
            return []
        current: list[str] = []
        first = parts[0]
        union_refs = self._instance_unions.get(first)
        if union_refs:
            current = list(union_refs)
        else:
            ref = self._instances.get(first) or self._symbols.get(first)
            if ref:
                current = [ref]
        if not current:
            return []
        for attr in parts[1:]:
            next_refs: list[str] = []
            for class_ref in current:
                # class_ref is "path::Service" or "path::Outer.Inner"
                class_qualified = (
                    class_ref.split("::", 1)[-1] if "::" in class_ref else class_ref
                )
                attr_type = self.resolve_class_attribute(class_qualified, attr)
                if attr_type:
                    next_refs.append(attr_type)
            if not next_refs:
                return []
            current = next_refs
        return current

    def is_class(self, name: str) -> bool:
        """Check whether a simple name was registered as a class definition."""
        return name in self._classes


def build_module_filter() -> frozenset[str]:
    """Build the module exclusion set from defaults + application config."""
    config = get_config()
    extra_excludes = set(config.graph.exclude_modules or [])
    force_includes = set(config.graph.include_modules or [])
    return frozenset((_DEFAULT_EXCLUDED_MODULES | extra_excludes) - force_includes)


def extract_graph_from_file(
    file_path: str,
    content: str,
    *,
    excluded_modules: frozenset[str] | None = None,
    module_index: ModuleIndex | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Parse a source file and extract all graph nodes and edges.

    Returns ``([], [])`` if the language is unsupported or parsing fails.
    """
    ctx = parse_file(file_path, content)
    if ctx is None:
        return [], []

    lc = get_lang_constants(ctx.lang_cfg.name)
    if lc is None:
        return [], []

    if excluded_modules is None:
        excluded_modules = build_module_filter()

    parser = GraphTreeSitterParser(
        ctx,
        excluded_modules=excluded_modules,
        module_index=module_index or {},
        lang_constants=lc,
    )
    return parser.extract()


class GraphTreeSitterParser(
    ImportHandlerMixin,
    TypeResolutionMixin,
    DefinitionHandlerMixin,
    AssignmentHandlerMixin,
    CallHandlerMixin,
    BaseTreeSitterParser,
):
    """One-shot tree-sitter graph extractor for a single source file.

    Composes handler mixins for imports, definitions, type resolution,
    assignments, and calls. The DFS dispatches to the appropriate handler
    based on AST node type.
    """

    def __init__(
        self,
        context: ParserContext,
        *,
        excluded_modules: frozenset[str],
        module_index: ModuleIndex | None = None,
        lang_constants: LangConstants | None = None,
    ) -> None:
        """Initialize the parser with file context and module filter."""
        super().__init__(context)
        self._excluded_modules = excluded_modules
        self._module_id: str = context.file_path
        self._nodes: list[GraphNode] = []
        self._edges: list[GraphEdge] = []
        self._module_index = module_index or {}
        self._file_ctx = FileContext(module_index=self._module_index)
        # Resolve from registry when not provided explicitly
        self._lang_constants = (
            lang_constants
            or get_lang_constants(context.lang_cfg.name)
        )

    @property
    def _lc(self) -> LangConstants:
        """Effective language constants."""
        assert self._lang_constants is not None, (
            f"No LangConstants for {self._ctx.lang_cfg.name}"
        )
        return self._lang_constants

    def extract(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Walk the syntax tree and return all graph nodes and edges."""
        tree = self.get_tree()

        module_node = GraphNode(
            id=self._module_id,
            kind=NodeKind.MODULE,
            file_path=self.file_path,
            start_line=1,
            end_line=tree.root_node.end_point[0] + 1,
            name=self.file_path,
            qualified_name=self.file_path,
        )
        self._nodes.append(module_node)

        self._dfs(tree.root_node, scope_stack=[])
        return self._nodes, self._edges

    def _dfs(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Recursively walk the AST, dispatching to type-specific handlers."""
        ntype = node.type
        lc = self._lc

        # Dispatch on AST node type. Scope-creating nodes (function/class)
        # return early -- they recurse into their own body with updated scope.
        if ntype in lc.import_types:
            self._handle_import(node, scope_stack=scope_stack)
        elif ntype in lc.function_scope_types:
            self._handle_function_def(node, scope_stack=scope_stack)
            return  # handler recurses with [*scope, func_name]
        elif ntype in (lc.class_scope_types + lc.extra_class_scope_types):
            self._handle_class_def(node, scope_stack=scope_stack)
            return  # handler recurses with [*scope, class_name]
        elif ntype in lc.call_types:
            self._handle_call(node, scope_stack=scope_stack)
        elif lc.has_decorator and ntype == "decorator":
            self._handle_decorator(node, scope_stack=scope_stack)
        elif ntype in lc.assignment_types:
            self._handle_assignment(node, scope_stack=scope_stack)
        elif lc.has_with_statement and ntype == "with_statement":
            self._handle_with_statement(node, scope_stack=scope_stack)

        # Non-scope nodes: continue DFS into children at same scope level
        for child in node.children:
            self._dfs(child, scope_stack=scope_stack)
