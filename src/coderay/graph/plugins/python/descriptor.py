"""Python graph extractor: AST type names and builtins."""

from __future__ import annotations

from dataclasses import dataclass, field

from coderay.parsing.builtins import PYTHON_ALL_BUILTINS


@dataclass
class PythonGraphDescriptor:
    """Tree-sitter dispatch and call filtering for Python graph lowering."""

    call_types: tuple[str, ...] = ("call",)
    assignment_types: tuple[str, ...] = ("assignment",)
    class_body_types: tuple[str, ...] = ("block",)
    typed_param_types: tuple[str, ...] = ("typed_parameter",)
    extra_class_scope_types: tuple[str, ...] = ()
    builtins: frozenset[str] = field(default_factory=lambda: PYTHON_ALL_BUILTINS)
    self_prefix: str = "self."
    super_prefixes: tuple[str, ...] = ("super().", "super.")
    decorator_types: tuple[str, ...] = ("decorator",)
    with_types: tuple[str, ...] = ("with_statement",)


PYTHON_GRAPH_DESCRIPTOR = PythonGraphDescriptor()
