"""CST traversal, node-ID, and annotation-resolution helpers for graph handlers."""

from __future__ import annotations

from collections.abc import Callable

from coderay.graph.lowering.name_bindings import NameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode

# ---------------------------------------------------------------------------
# Base-class / heritage CST helpers
# ---------------------------------------------------------------------------

# Node types that carry superclass lists — differs across languages:
# Python: argument_list / superclass  |  JS/TS: extends_clause / class_heritage
BASE_CLASS_NODE_TYPES = (
    "argument_list",
    "superclass",
    "extends_clause",
    "class_heritage",
)


def list_base_names_from_arg_list(
    arg_list_node: TSNode, node_text: Callable[[TSNode], str]
) -> list[str]:
    # class Foo(Base, Mixin)  ->  ["Base", "Mixin"]
    base_types = (
        "identifier",
        "dotted_name",
        "attribute",
        "type_identifier",
        "member_expression",
    )
    result: list[str] = []
    candidates = arg_list_node.named_children
    # JS/TS extends_clause / class_heritage store the value under a field.
    if not candidates and arg_list_node.type in ("extends_clause", "class_heritage"):
        value = arg_list_node.child_by_field_name("value")
        if value:
            candidates = [value]
    for arg in candidates:
        if arg.type in base_types:
            name = node_text(arg)
            if name:
                result.append(name)
        elif arg.type in ("generic_type", "subscript"):
            # Generic base: List[T] or Base[T]  ->  take the outer name only.
            if arg.named_children:
                name = node_text(arg.named_children[0])
                if name:
                    result.append(name)
    return result


def resolve_base_class_name(raw: str, bindings: NameBindings) -> str:
    """Resolve a base class name through bindings.

    e.g. "mod.Base" -> "path/mod.py::Base".
    """
    parts = raw.split(".")
    if len(parts) == 1:
        return bindings.resolve(raw) or raw
    # Dotted: resolve the prefix module alias, keep the suffix as-is.
    prefix_resolved = bindings.resolve(parts[0])
    if prefix_resolved:
        return f"{prefix_resolved}.{'.'.join(parts[1:])}"
    return raw


# ---------------------------------------------------------------------------
# Node-ID helper
# ---------------------------------------------------------------------------


def caller_id_for_scope(file_path: str, scope_stack: list[str]) -> str:
    """Node ID for the current scope. e.g. ["Foo", "bar"] -> "a.py::Foo.bar"."""
    if scope_stack:
        return f"{file_path}::{'.'.join(scope_stack)}"
    return file_path  # module-level scope


# ---------------------------------------------------------------------------
# Config-driven CST function lookup — no language subclasses needed,
# node-type sets come from lang_cfg.cst.
# ---------------------------------------------------------------------------


def find_class_node(parser: BaseTreeSitterParser, class_name: str) -> TSNode | None:
    """Find a class definition node by name in the parsed tree."""
    class_types = parser.lang_cfg.cst.class_scope_types

    def search(n: TSNode) -> TSNode | None:
        if n.type in class_types:
            name_node = n.child_by_field_name("name") or (
                n.named_children[0] if n.named_children else None
            )
            if name_node and parser.node_text(name_node) == class_name:
                return n
        for c in n.children:
            found = search(c)
            if found:
                return found
        return None

    return search(parser.get_tree().root_node)


def find_top_level_function(parser: BaseTreeSitterParser, name: str) -> TSNode | None:
    """Find a module-scope function node by name (works for Python and JS/TS)."""
    fn_types = parser.lang_cfg.cst.function_scope_types  # e.g. ("function_definition",)

    def search(n: TSNode) -> TSNode | None:
        # identifier_from_node handles arrow functions (variable_declarator wrapping).
        if n.type in fn_types and parser.identifier_from_node(n) == name:
            return n
        for c in n.children:
            found = search(c)
            if found:
                return found
        return None

    return search(parser.get_tree().root_node)


def find_method_in_class(
    parser: BaseTreeSitterParser, class_name: str, method_name: str
) -> TSNode | None:
    """Find a method node inside a named class (all languages)."""
    class_node = find_class_node(parser, class_name)
    if not class_node:
        return None
    body_types = parser.lang_cfg.cst.class_body_types  # e.g. ("block",)
    fn_types = parser.lang_cfg.cst.function_scope_types
    for child in class_node.children:
        if child.type not in body_types:
            continue
        for stmt in child.children:
            node = _unwrap_decorated(stmt)  # strip @decorators for Python
            if (
                node.type in fn_types
                and parser.identifier_from_node(node) == method_name
            ):
                return node
    return None


def _unwrap_decorated(node: TSNode) -> TSNode:
    """Return the inner def/class from a decorated_definition, or node itself."""
    if node.type == "decorated_definition":
        # decorated_definition: decorator* (function_definition | class_definition)
        for c in node.children:
            if c.type != "decorator":
                return c
    return node


def find_enclosing_class_from_node(
    parser: BaseTreeSitterParser, node: TSNode
) -> str | None:
    """Walk up the CST and return the innermost enclosing class qualified name.

    e.g. node inside Outer.Inner  ->  "Outer.Inner"
    """
    current = node.parent
    class_names: list[str] = []
    class_scope_types = parser.lang_cfg.cst.class_scope_types
    while current:
        if current.type in class_scope_types:
            name_node = current.child_by_field_name("name") or (
                current.named_children[0] if current.named_children else None
            )
            if name_node:
                name = parser.node_text(name_node)
                if name:
                    class_names.append(name)
        current = current.parent
    if not class_names:
        return None
    class_names.reverse()  # collected inner-to-outer; reverse for qualified form
    return ".".join(class_names)


def get_enclosing_function_node(
    parser: BaseTreeSitterParser, node: TSNode
) -> TSNode | None:
    """Walk up the CST and return the innermost enclosing function definition node."""
    current = node.parent
    fn_types = parser.lang_cfg.cst.function_scope_types
    while current:
        if current.type in fn_types:
            return current
        current = current.parent
    return None


# ---------------------------------------------------------------------------
# Annotation + CST combined — need both parser (file_path, CST) and bindings.
# ---------------------------------------------------------------------------


def resolve_type_texts(
    parser: BaseTreeSitterParser,
    bindings: NameBindings,
    type_text: str | None,
    *,
    enclosing_func_node: TSNode | None = None,
) -> list[str]:
    """Resolve annotation text to qualified class refs.

    e.g. "Foo | Bar" -> ["path/a.py::Foo", "path/b.py::Bar"]
    """
    use_self = bool(enclosing_func_node) and is_bare_self_annotation(type_text)
    # For `Self` annotations, find the class that owns the enclosing function.
    enc = (
        find_enclosing_class_from_node(parser, enclosing_func_node)
        if use_self
        else None
    )
    return resolve_annotation_type_texts(
        type_text,
        file_path=parser.file_path,
        resolve=bindings.resolve,
        use_self_semantics=use_self,
        enclosing_class_qualified=enc,
    )


def get_return_type_from_func_node(
    parser: BaseTreeSitterParser, bindings: NameBindings, func_node: TSNode
) -> str | None:
    """Read the return-type annotation of a function node and resolve it."""
    # Python uses "return_type", JS/TS uses "type".
    type_node = func_node.child_by_field_name(
        "return_type"
    ) or func_node.child_by_field_name("type")
    if not type_node:
        return None
    refs = resolve_type_texts(
        parser, bindings, parser.node_text(type_node), enclosing_func_node=func_node
    )
    return refs[0] if refs else None


def get_function_return_type(
    parser: BaseTreeSitterParser, bindings: NameBindings, callee_name: str
) -> str | None:
    """Look up a callee by name and return its annotated return type, or None."""
    # "Foo.bar" -> find method; "foo" -> find top-level function.
    if "." in callee_name:
        class_name, method_name = callee_name.split(".", 1)
        func_node = find_method_in_class(parser, class_name, method_name)
    else:
        func_node = find_top_level_function(parser, callee_name)
    return (
        get_return_type_from_func_node(parser, bindings, func_node)
        if func_node
        else None
    )


def extract_type_from_typed_param(
    parser: BaseTreeSitterParser, bindings: NameBindings, param_node: TSNode
) -> tuple[str, list[str]] | None:
    """Extract (param_name, type_refs) from a typed parameter CST node.

    e.g. `x: Foo` -> ("x", ["path/a.py::Foo"])
    """
    name_node = param_node.child_by_field_name("name") or (
        param_node.children[0] if param_node.children else None
    )
    if not name_node:
        return None
    pname = parser.node_text(name_node)
    type_node = param_node.child_by_field_name("type")
    if type_node is None:
        # Some grammars wrap the type under a bare "type" child instead of a field.
        for c in param_node.children:
            if c.type == "type":
                type_node = c
                break
    if not type_node:
        return None
    # param_node.parent = parameters, parameters.parent = function_definition.
    parent = param_node.parent
    enclosing = parent.parent if parent and parent.parent else None
    type_refs = resolve_type_texts(
        parser, bindings, parser.node_text(type_node), enclosing_func_node=enclosing
    )
    return (pname, type_refs) if type_refs else None


def get_typed_parameters(
    parser: BaseTreeSitterParser, bindings: NameBindings, func_node: TSNode
) -> list[tuple[str, list[str]]]:
    """Return (param_name, type_refs) for every typed parameter of a function."""
    params = func_node.child_by_field_name("parameters")
    if not params:
        return []
    param_types = parser.lang_cfg.cst.typed_param_types  # e.g. ("typed_parameter",)
    result: list[tuple[str, list[str]]] = []
    for child in params.children:
        if child.type in param_types:
            extracted = extract_type_from_typed_param(parser, bindings, child)
            if extracted:
                result.append(extracted)
    return result


def get_parameter_type_hint(
    parser: BaseTreeSitterParser,
    bindings: NameBindings,
    func_node: TSNode,
    param_name: str,
) -> str | None:
    """Return the first resolved type ref for a named parameter, or None."""
    for name, refs in get_typed_parameters(parser, bindings, func_node):
        if name == param_name:
            return refs[0] if refs else None
    return None


# ---------------------------------------------------------------------------
# Pure annotation string resolution (no CST, no bindings object — just resolve fn)
# ---------------------------------------------------------------------------


def is_bare_self_annotation(type_text: str | None) -> bool:
    """True if annotation text is exactly ``Self`` (handles quotes)."""
    if not type_text:
        return False
    text = type_text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1]
    return text == "Self"


def resolve_annotation_type_texts(
    type_text: str | None,
    *,
    file_path: str,
    resolve: Callable[[str], str | None],
    use_self_semantics: bool = False,
    enclosing_class_qualified: str | None = None,
) -> list[str]:
    """Resolve annotation text to a list of qualified class refs.

    "Foo | Bar" -> ["path/a.py::Foo", "path/b.py::Bar"]
    With use_self_semantics=True, bare "Self" -> ["path/a.py::EnclosingClass"].
    """
    if not type_text:
        return []
    text = type_text.strip()
    if not text:
        return []
    # Strip forward-reference quotes: "Foo" -> Foo
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1]
    if use_self_semantics and text == "Self":
        if enclosing_class_qualified:
            return [f"{file_path}::{enclosing_class_qualified}"]
        return []
    parts = [p.strip() for p in text.split("|")]
    result: list[str] = []
    for part in parts:
        if not part or part in ("None", "NoneType"):
            continue
        if "." in part and not part[0].isupper():
            # module.ClassName alias: resolve the module prefix.
            alias, _, attr = part.partition(".")
            if attr and attr[0].isupper():
                resolved_alias = resolve(alias)
                if resolved_alias:
                    result.append(f"{resolved_alias}::{attr}")
            continue
        if not part[0].isupper():
            continue  # skip builtins, lowercase names
        resolved = resolve(part)
        result.append(resolved or f"{file_path}::{part}")
    return result


def resolve_annotation_type_text(
    type_text: str | None,
    *,
    file_path: str,
    resolve: Callable[[str], str | None],
) -> str | None:
    """First result from resolve_annotation_type_texts, or None."""
    refs = resolve_annotation_type_texts(
        type_text, file_path=file_path, resolve=resolve
    )
    return refs[0] if refs else None
