"""JS/TS graph lowering: policy not covered by ``CstDispatchConfig``."""

from __future__ import annotations

from dataclasses import dataclass, field

from coderay.parsing.builtins import JS_TS_BUILTINS


@dataclass
class JsTsGraphDescriptor:
    """Class body shape, typed params, builtins, and call prefixes."""

    class_body_types: tuple[str, ...] = ("block", "class_body")
    typed_param_types: tuple[str, ...] = (
        "typed_parameter",
        "required_parameter",
        "optional_parameter",
    )
    builtins: frozenset[str] = field(default_factory=lambda: JS_TS_BUILTINS)
    self_prefix: str = "this."
    super_prefixes: tuple[str, ...] = ("super().", "super.")


JS_TS_GRAPH_DESCRIPTOR = JsTsGraphDescriptor()
