from __future__ import annotations

import builtins
import logging

from coderay.core.config import get_config
from coderay.core.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from coderay.parsing.base import BaseTreeSitterParser, ParserContext, parse_file

logger = logging.getLogger(__name__)

_PYTHON_BUILTINS: frozenset[str] = frozenset(
    name for name in dir(builtins) if not name.startswith("_")
)

_DEFAULT_EXCLUDED_MODULES: frozenset[str] = frozenset(
    {
        "builtins",
        "typing",
        "typing_extensions",
        "abc",
        "__future__",
    }
)


class FileContext:
    """Tracks name bindings within a single file during graph extraction.

    Provides unified name resolution for imports, definitions, instances,
    and aliases encountered during a single-file extraction pass.  Every
    registration overwrites the previous binding for the same local name
    (last-write-wins), which mirrors Python's runtime semantics.
    """

    def __init__(self) -> None:
        self._symbols: dict[str, str] = {}
        self._instances: dict[str, str] = {}
        self._classes: set[str] = set()

    def register_import(self, local_name: str, qualified_name: str) -> None:
        """Register an imported symbol binding."""
        self._symbols[local_name] = qualified_name

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
        """Resolve ``obj.method()`` when *obj* is a tracked instance."""
        class_ref = self._instances.get(obj_name)
        if class_ref is None:
            return None
        return f"{class_ref}.{method_name}"

    def is_class(self, name: str) -> bool:
        """Check whether a simple name was registered as a class definition."""
        return name in self._classes


def build_module_filter() -> frozenset[str]:
    """Build the module exclusion set from defaults + application config.

    Returns:
        Frozen set of module names/prefixes whose symbols are excluded
        from CALLS and IMPORTS edges.
    """
    config = get_config()
    graph_cfg = getattr(config, "graph", None) or {}
    if not isinstance(graph_cfg, dict):
        graph_cfg = {}
    extra_excludes = set(graph_cfg.get("exclude_modules") or [])
    force_includes = set(graph_cfg.get("include_modules") or [])
    return frozenset((_DEFAULT_EXCLUDED_MODULES | extra_excludes) - force_includes)


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


def extract_graph_from_file(
    file_path: str,
    content: str,
    *,
    excluded_modules: frozenset[str] | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Parse a source file and extract all graph nodes and edges.

    Args:
        file_path: Path of the source file.
        content: Source code contents.
        excluded_modules: Pre-computed module filter.  When ``None``,
            ``build_module_filter()`` is called (hits the global config).

    Returns:
        Tuple of (nodes, edges). Returns ``([], [])`` if the language
        is unsupported or parsing fails.
    """
    ctx = parse_file(file_path, content)
    if ctx is None:
        return [], []

    if excluded_modules is None:
        excluded_modules = build_module_filter()

    parser = GraphTreeSitterParser(ctx, excluded_modules=excluded_modules)
    try:
        return parser.extract()
    except Exception:
        return [], []


class GraphTreeSitterParser(BaseTreeSitterParser):
    """One-shot tree-sitter based graph extractor for a single source file."""

    def __init__(
        self,
        context: ParserContext,
        *,
        excluded_modules: frozenset[str],
    ) -> None:
        """Initialize the parser with file context and module filter."""
        super().__init__(context)
        self._excluded_modules = excluded_modules
        self._module_id: str = context.file_path
        self._nodes: list[GraphNode] = []
        self._edges: list[GraphEdge] = []
        self._file_ctx = FileContext()

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

    # ------------------------------------------------------------------
    # Tree traversal
    # ------------------------------------------------------------------

    def _dfs(self, node, *, scope_stack: list[str]) -> None:
        """Recursively walk the syntax tree, dispatching to type-specific handlers.

        Lambdas and comprehensions create implicit scopes in Python but are
        currently traversed without scope adjustment — calls inside them are
        attributed to the enclosing function.
        """
        ntype = node.type
        lang_cfg = self._ctx.lang_cfg

        if ntype in lang_cfg.import_types:
            self._handle_import(node)
        elif ntype in lang_cfg.function_scope_types:
            self._handle_function_def(node, scope_stack=scope_stack)
            return
        elif ntype in (
            lang_cfg.class_scope_types + lang_cfg.graph.extra_class_scope_types
        ):
            self._handle_class_def(node, scope_stack=scope_stack)
            return
        elif ntype in lang_cfg.graph.call_types:
            self._handle_call(node, scope_stack=scope_stack)
        elif ntype == "assignment":
            self._handle_assignment(node, scope_stack=scope_stack)
        # TODO: handle decorated_definition → emit DECORATES edges linking
        #  each decorator to the wrapped function/class for blast-radius
        #  visibility (duplication with CALLS edges is acceptable)

        for child in node.children:
            self._dfs(child, scope_stack=scope_stack)

    # ------------------------------------------------------------------
    # Import handling
    # ------------------------------------------------------------------

    def _handle_import(self, node) -> None:
        """Create IMPORTS edges and register names in the file context.

        Uses prev_sibling relationships to identify the module name (node
        right after ``from`` or ``import`` keyword) and imported names,
        rather than tracking positional state.  Handles bare imports,
        from-imports, aliased imports, and future imports.  Imports from
        excluded modules are still registered in FileContext (needed for
        resolution) but do not produce IMPORTS edges.
        """
        # TODO: handle wildcard imports (``from module import *``)
        ntype = node.type
        module: list[str] = []
        imported: list[tuple[str, str]] = []

        for child in node.children:
            prev = child.prev_sibling
            prev_type = prev.type if prev else None

            if ntype == "import_from_statement":
                # Module name: the node right after "from"
                if prev_type == "from":
                    text = self._resolve_import_text(child)
                    if text:
                        module.append(text)
                    continue
                # Imported names: dotted_name / identifier / aliased_import
                # after the "import" keyword (siblings past the module)
                self._collect_import_name(child, imported)

            elif ntype == "import_statement":
                # Every dotted_name / aliased_import after "import" keyword
                if prev_type == "import" or prev_type == ",":
                    self._collect_bare_import(child, module, imported)

            elif ntype == "future_import_statement":
                if prev_type == "from":
                    module.append(self.node_text(child).strip())
                    continue
                self._collect_import_name(child, imported)

        # from X import Y [as Z], from __future__ import X
        if module and imported:
            mod_name = module[0]
            is_excluded = mod_name in self._excluded_modules
            for original, local in imported:
                qualified = f"{mod_name}::{original}"
                # Always register so resolution works even for excluded modules
                if ntype != "future_import_statement":
                    self._file_ctx.register_import(local, qualified)
                # Skip IMPORTS edge for excluded modules
                if is_excluded:
                    continue
                self._edges.append(
                    GraphEdge(
                        source=self._module_id,
                        target=qualified,
                        kind=EdgeKind.IMPORTS,
                    )
                )

        # bare import X [as Y] — edge per module, register accessible name
        if ntype == "import_statement":
            for mod_text, local in imported:
                self._file_ctx.register_import(local, mod_text)
                if mod_text in self._excluded_modules:
                    continue
                self._edges.append(
                    GraphEdge(
                        source=self._module_id,
                        target=mod_text,
                        kind=EdgeKind.IMPORTS,
                    )
                )

    def _resolve_import_text(self, child) -> str | None:
        """Resolve the text of an import module node, handling relative paths."""
        text = self.node_text(child).strip()
        if text and text[0] == ".":
            return _resolve_relative_import(self._module_id, text)
        return text or None

    def _collect_import_name(self, child, names: list[tuple[str, str]]) -> None:
        """Collect an imported name (``Y`` or ``Y as Z``) into *names*."""
        ctype = child.type
        if ctype in ("dotted_name", "identifier"):
            name = self.node_text(child).strip()
            names.append((name, name))
        elif ctype == "aliased_import":
            original, alias = self._parse_aliased_import(child)
            if original:
                names.append((original, alias or original))

    def _collect_bare_import(
        self,
        child,
        module: list[str],
        imported: list[tuple[str, str]],
    ) -> None:
        """Collect a bare-import target (``X`` or ``X as Y``) into *imported*."""
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
                    text = _resolve_relative_import(self._module_id, text) or text
                local = alias or text.split(".")[0]
                module.append(text)
                imported.append((text, local))

    def _parse_aliased_import(self, node) -> tuple[str | None, str | None]:
        """Extract ``(original_name, alias)`` from an ``aliased_import`` node."""
        original: str | None = None
        alias: str | None = None
        for child in node.children:
            if child.type in ("dotted_name", "identifier"):
                if original is None:
                    original = self.node_text(child).strip()
                else:
                    alias = self.node_text(child).strip()
        return original, alias

    # ------------------------------------------------------------------
    # Definition handling
    # ------------------------------------------------------------------

    def _handle_function_def(self, node, *, scope_stack: list[str]) -> None:
        """Create a FUNCTION node and DEFINES edge, then recurse into the body."""
        name = self.identifier_from_node(node)
        if not name:
            return

        # Build fully qualified name: e.g. ClassName.method or just func_name
        qualified = ".".join([*scope_stack, name])
        node_id = f"{self.file_path}::{qualified}"

        self._nodes.append(
            GraphNode(
                id=node_id,
                kind=NodeKind.FUNCTION,
                file_path=self.file_path,
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

        # Register in FileContext so calls resolve to the full node_id.
        # Top-level: ``my_func()`` → node_id
        # Class methods: ``ClassName.method()`` → node_id (via qualified name)
        if not scope_stack:
            self._file_ctx.register_definition(name, node_id)
        else:
            self._file_ctx.register_definition(qualified, node_id)

        # Recurse into the function body under a new scope
        new_scope = [*scope_stack, name]
        for child in node.children:
            self._dfs(child, scope_stack=new_scope)

    def _handle_class_def(self, node, *, scope_stack: list[str]) -> None:
        """Create a CLASS node, DEFINES + INHERITS edges, then recurse."""
        name = self.identifier_from_node(node)
        if not name:
            return

        # Build qualified name: e.g. OuterClass.InnerClass
        qualified = ".".join([*scope_stack, name])
        node_id = f"{self.file_path}::{qualified}"

        self._nodes.append(
            GraphNode(
                id=node_id,
                kind=NodeKind.CLASS,
                file_path=self.file_path,
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

        # Extract base classes from the superclass list and resolve them
        # through FileContext so INHERITS targets are fully qualified
        # (e.g. "Animal" → "mymodule::Animal" if imported).
        for child in node.children:
            if child.type in ("argument_list", "superclass", "extends_clause"):
                for arg in child.children:
                    if arg.type in (
                        "identifier",
                        "dotted_name",
                        "attribute",
                        "type_identifier",
                    ):
                        if base_name := self.node_text(arg):
                            resolved = self._resolve_base_class(base_name)
                            self._edges.append(
                                GraphEdge(
                                    source=node_id,
                                    target=resolved,
                                    kind=EdgeKind.INHERITS,
                                )
                            )

        # Register before recursion so nested classes can see the outer class
        self._file_ctx.register_definition(name, node_id, is_class=True)

        new_scope = [*scope_stack, name]
        for child in node.children:
            self._dfs(child, scope_stack=new_scope)

    def _resolve_base_class(self, raw: str) -> str:
        """Resolve a base class name through FileContext.

        Handles single names (``Animal``), dotted names (``abc.ABC``),
        and falls back to the raw text when the name is unknown.
        """
        parts = raw.split(".")
        if len(parts) == 1:
            return self._file_ctx.resolve(raw) or raw

        # Dotted: resolve the prefix (e.g. abc → abc module) and rebuild
        prefix = parts[0]
        suffix = ".".join(parts[1:])
        prefix_resolved = self._file_ctx.resolve(prefix)
        if prefix_resolved:
            return f"{prefix_resolved}.{suffix}"
        return raw

    # ------------------------------------------------------------------
    # Assignment handling
    # ------------------------------------------------------------------

    def _handle_assignment(self, node, *, scope_stack: list[str]) -> None:
        """Track simple name aliases (``my_func = imported_func``).

        Only handles ``name = expr`` where expr is a known identifier or
        single-dot attribute.  Skips tuple unpacking, augmented assignments,
        and deep attribute chains.  Instantiation tracking (``x = MyClass()``)
        is handled separately in ``_maybe_track_instantiation``.
        """
        children = node.children
        # assignment AST: [lhs, =, rhs] — fewer than 3 means malformed/unsupported
        if len(children) < 3:
            return

        # children[0] = target, children[-1] = value
        # [-1] handles annotated assignments (x: int = val → 5 children)
        lhs = children[0]
        rhs = children[-1]

        # TODO: handle tuple unpacking (a, b = func()), starred, subscript targets
        # TODO: handle self.var = expr (attribute LHS) for composition tracking —
        #  would allow resolving self.var.method() calls later
        if lhs.type != "identifier":
            return

        lhs_name = self.node_text(lhs)

        if rhs.type == "identifier":
            # my_func = imported_func
            rhs_name = self.node_text(rhs)
            resolved = self._file_ctx.resolve(rhs_name)
            if resolved:
                self._file_ctx.register_alias(lhs_name, resolved)
        elif rhs.type == "attribute":
            # TODO: support deep attribute chains (a.b.c) — currently single-dot only
            rhs_text = self.node_text(rhs)
            parts = rhs_text.split(".")
            if len(parts) == 2:
                prefix, attr = parts
                prefix_resolved = self._file_ctx.resolve(prefix)
                if prefix_resolved:
                    self._file_ctx.register_alias(
                        lhs_name, f"{prefix_resolved}::{attr}"
                    )

    # ------------------------------------------------------------------
    # Call handling
    # ------------------------------------------------------------------

    def _handle_call(self, node, *, scope_stack: list[str]) -> None:
        """Create a CALLS edge from the enclosing scope to the callee."""
        caller_id = (
            f"{self.file_path}::{'.'.join(scope_stack)}"
            if scope_stack
            else self._module_id
        )

        # Use the grammar's "function" field for the callee expression
        callee_node = node.child_by_field_name("function")
        if callee_node is None:
            return
        raw_callee = self.node_text(callee_node)
        if not raw_callee:
            return

        # Resolve first, then decide whether to filter — this avoids
        # false positives when a project defines a symbol that shadows
        # a builtin name (e.g. a class with a .join() method).
        callee_name = self._resolve_callee(raw_callee, scope_stack)

        if self._is_excluded(callee_name, raw_callee):
            return

        if callee_name:
            self._edges.append(
                GraphEdge(
                    source=caller_id,
                    target=callee_name,
                    kind=EdgeKind.CALLS,
                )
            )

        self._maybe_track_instantiation(node, raw_callee)

    def _resolve_callee(self, raw: str, scope_stack: list[str]) -> str:
        """Resolve a raw callee expression to a qualified target name.

        Returns:
            Fully qualified target when resolution succeeds, otherwise
            the bare terminal name as a best-effort fallback.
        """
        # self.method() / this.method() → file::Class.method
        if raw.startswith(("self.", "this.")):
            suffix = raw.split(".", 1)[1]
            parts = suffix.split(".")
            method = parts[-1]

            if len(parts) == 1:
                class_qualified = self._find_enclosing_class(scope_stack)
                if class_qualified:
                    return f"{self.file_path}::{class_qualified}.{method}"

            # TODO: resolve self.obj.method() via instance tracking on
            #  self.obj — requires attribute-LHS assignment tracking
            return method

        parts = raw.split(".")

        # Simple name: func() → resolve via FileContext
        if len(parts) == 1:
            name = parts[0]
            resolved = self._file_ctx.resolve(name)
            return resolved if resolved else name

        obj_name = parts[0]
        method_name = parts[-1]

        # instance.method() → Class.method via instance tracking
        method_resolved = self._file_ctx.resolve_method_call(obj_name, method_name)
        if method_resolved:
            return method_resolved

        # obj.attr() → resolve obj prefix, keep full tail (a.b.c → resolved_a.b.c)
        # TODO: resolve intermediate segments via type inference for deeper
        #  chains (e.g. knowing what type a.b returns to resolve a.b.c)
        obj_resolved = self._file_ctx.resolve(obj_name)
        if obj_resolved:
            tail = ".".join(parts[1:])
            return f"{obj_resolved}.{tail}"

        return method_name

    def _is_excluded(self, resolved: str, raw: str) -> bool:
        """Check whether a resolved callee belongs to an excluded module.

        Returns:
            True if the call should be filtered out of the graph.
        """
        # If resolution produced a qualified name, check the module prefix
        if "::" in resolved:
            module_part = resolved.split("::")[0]
            if module_part in self._excluded_modules:
                return True

        # Unresolved bare names that match Python builtins (print, len, etc.)
        bare = raw.rsplit(".", 1)[-1]
        if resolved == bare and bare in _PYTHON_BUILTINS:
            return True

        return False

    def _find_enclosing_class(self, scope_stack: list[str]) -> str | None:
        """Find the innermost enclosing class name from the scope stack."""
        for i in range(len(scope_stack) - 1, -1, -1):
            if self._file_ctx.is_class(scope_stack[i]):
                return ".".join(scope_stack[: i + 1])
        return None

    def _maybe_track_instantiation(self, call_node, raw_callee: str) -> None:
        """If the call is ``x = SomeClass()``, track *x* as an instance."""
        parent = call_node.parent
        if parent is None or parent.type != "assignment":
            return

        # TODO: handle self.var = SomeClass() (attribute LHS) — currently
        #  only tracks simple name assignments like x = SomeClass()
        lhs = parent.children[0] if parent.children else None
        if lhs is None or lhs.type != "identifier":
            return

        var_name = self.node_text(lhs)
        callee_base = raw_callee.rsplit(".", 1)[-1]
        if not callee_base:
            return

        resolved = self._file_ctx.resolve(callee_base)
        is_known_class = self._file_ctx.is_class(callee_base)
        is_likely_class = bool(callee_base[0].isupper() and resolved is not None)

        if is_known_class or is_likely_class:
            self._file_ctx.register_instance(var_name, resolved or callee_base)
