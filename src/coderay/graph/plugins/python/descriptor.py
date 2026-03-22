"""Python graph lowering: policy not covered by ``CstDispatchConfig``."""

from __future__ import annotations

from dataclasses import dataclass, field

from coderay.parsing.builtins import PYTHON_ALL_BUILTINS


@dataclass
class PythonGraphDescriptor:
    """Call filtering, class body shape, and builtins (not node dispatch)."""

    class_body_types: tuple[str, ...] = ("block",)
    typed_param_types: tuple[str, ...] = ("typed_parameter",)
    builtins: frozenset[str] = field(default_factory=lambda: PYTHON_ALL_BUILTINS)
    self_prefix: str = "self."
    super_prefixes: tuple[str, ...] = ("super().", "super.")


PYTHON_GRAPH_DESCRIPTOR = PythonGraphDescriptor()
