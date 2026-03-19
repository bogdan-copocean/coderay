"""Language-specific constants for graph extraction.

Plugins provide these instead of relying on lang_cfg, eliminating
language branching in handlers.
"""

from __future__ import annotations

import builtins
import io
from collections.abc import Callable
from dataclasses import dataclass

# Builtin function/type names (print, len, int, ...) -- anything unresolved
# matching these is noise, not a real CALLS edge.
_PYTHON_BUILTINS: frozenset[str] = frozenset(
    name for name in dir(builtins) if not name.startswith("_")
)

# Common methods on builtin types (list.append, dict.get, str.split, ...).
# Introspected at import time so the set stays current with the Python version.
_BUILTIN_TYPES: tuple[type, ...] = (
    list, dict, set, tuple, str, bytes, frozenset,
    io.IOBase, io.RawIOBase, io.BufferedIOBase, io.TextIOBase,
)
_PYTHON_BUILTIN_METHODS: frozenset[str] = frozenset(
    name
    for cls in _BUILTIN_TYPES
    for name in dir(cls)
    if not name.startswith("_") and callable(getattr(cls, name, None))
)
_JS_BUILTINS: frozenset[str] = frozenset(
    {
        "fetch",
        "console",
        "JSON",
        "Promise",
        "Map",
        "Set",
        "Array",
        "Object",
        "Number",
        "String",
        "Boolean",
        "Symbol",
        "BigInt",
        "Math",
        "Date",
        "RegExp",
        "Error",
        "parseInt",
        "parseFloat",
        "isNaN",
        "isFinite",
        "eval",
        "encodeURI",
        "decodeURI",
        "encodeURIComponent",
        "decodeURIComponent",
        "setTimeout",
        "setInterval",
        "clearTimeout",
        "clearInterval",
        "requestAnimationFrame",
        "cancelAnimationFrame",
    }
)


@dataclass(frozen=True)
class LangConstants:
    """Constants for graph extraction; no lang_cfg branching."""

    import_types: tuple[str, ...]
    function_scope_types: tuple[str, ...]
    class_scope_types: tuple[str, ...]
    extra_class_scope_types: tuple[str, ...]
    call_types: tuple[str, ...]
    assignment_types: tuple[str, ...]
    class_body_types: tuple[str, ...]
    typed_param_types: tuple[str, ...]
    builtins: frozenset[str]
    self_prefixes: tuple[str, ...]  # ("self.",) or ("this.",)
    super_prefixes: tuple[str, ...]  # ("super().", "super.") or ("super().", "super.")
    has_decorator: bool
    has_with_statement: bool
    has_property: bool
    import_handler_factory: Callable[[], object]


def python_lang_constants() -> LangConstants:
    """Return constants for Python graph extraction."""
    from coderay.graph._handlers.lang.python.imports import PythonImportHandler

    return LangConstants(
        import_types=(
            "import_statement",
            "import_from_statement",
            "future_import_statement",
        ),
        function_scope_types=("function_definition",),
        class_scope_types=("class_definition",),
        extra_class_scope_types=(),
        call_types=("call",),
        assignment_types=("assignment",),
        class_body_types=("block",),
        typed_param_types=("typed_parameter",),
        builtins=_PYTHON_BUILTINS | _PYTHON_BUILTIN_METHODS,
        self_prefixes=("self.",),
        super_prefixes=("super().", "super."),
        has_decorator=True,
        has_with_statement=True,
        has_property=True,
        import_handler_factory=lambda: PythonImportHandler(),
    )


def js_ts_lang_constants() -> LangConstants:
    """Return constants for JS/TS graph extraction."""
    from coderay.graph._handlers.lang.js_ts.imports import JsTsImportHandler

    return LangConstants(
        import_types=("import_statement",),
        function_scope_types=(
            "function_declaration",
            "method_definition",
            "arrow_function",
        ),
        class_scope_types=("class_declaration",),
        extra_class_scope_types=("interface_declaration",),
        call_types=("call_expression",),
        assignment_types=("assignment_expression", "variable_declarator"),
        class_body_types=("block", "class_body"),
        typed_param_types=(
            "typed_parameter",
            "required_parameter",
            "optional_parameter",
        ),
        builtins=_JS_BUILTINS,
        self_prefixes=("this.",),
        super_prefixes=("super().", "super."),
        has_decorator=False,
        has_with_statement=False,
        has_property=False,
        import_handler_factory=lambda: JsTsImportHandler(),
    )


def from_lang_cfg(lang_cfg) -> LangConstants:
    """Build LangConstants from a full language config (e.g. GoConfig)."""
    from coderay.graph._handlers.lang.registry import get_import_handler

    def _handler_factory():
        return get_import_handler(lang_cfg.name)

    return LangConstants(
        import_types=lang_cfg.import_types,
        function_scope_types=lang_cfg.function_scope_types,
        class_scope_types=lang_cfg.class_scope_types,
        extra_class_scope_types=lang_cfg.graph.extra_class_scope_types,
        call_types=lang_cfg.graph.call_types,
        assignment_types=lang_cfg.graph.assignment_types,
        class_body_types=lang_cfg.graph.class_body_types,
        typed_param_types=lang_cfg.graph.typed_param_types,
        builtins=frozenset(),
        self_prefixes=(),
        super_prefixes=(),
        has_decorator=bool(lang_cfg.decorator_scope_types),
        has_with_statement=lang_cfg.name == "python",
        has_property=lang_cfg.name == "python",
        import_handler_factory=_handler_factory,
    )
