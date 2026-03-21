"""JavaScript/TypeScript graph lowering: AST type names and builtins."""

from __future__ import annotations

from dataclasses import dataclass, field

from coderay.parsing.builtins import JS_TS_BUILTINS


@dataclass
class JsTsGraphDescriptor:
    """Tree-sitter dispatch and call filtering for JS/TS graph lowering."""

    call_types: tuple[str, ...] = ("call_expression",)
    assignment_types: tuple[str, ...] = ("assignment_expression", "variable_declarator")
    class_body_types: tuple[str, ...] = ("block", "class_body")
    typed_param_types: tuple[str, ...] = (
        "typed_parameter",
        "required_parameter",
        "optional_parameter",
    )
    extra_class_scope_types: tuple[str, ...] = ("interface_declaration",)
    builtins: frozenset[str] = field(default_factory=lambda: JS_TS_BUILTINS)
    self_prefix: str = "this."
    super_prefixes: tuple[str, ...] = ("super().", "super.")
    decorator_types: tuple[str, ...] = ()
    with_types: tuple[str, ...] = ()
    tracks_property_types: bool = False


JS_TS_GRAPH_DESCRIPTOR = JsTsGraphDescriptor()
