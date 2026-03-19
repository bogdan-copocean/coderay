"""Language-specific constants for graph extraction.

Single lookup via ``get_lang_constants(lang_name)`` — no separate factory
functions or bridge layers needed by callers.
"""

from __future__ import annotations

import builtins
import io
from collections.abc import Callable
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Python builtins — introspected so the sets stay current with the runtime.
# ---------------------------------------------------------------------------

_PYTHON_BUILTINS: frozenset[str] = frozenset(
    name for name in dir(builtins) if not name.startswith("_")
)

_BUILTIN_TYPES: tuple[type, ...] = (
    list,
    dict,
    set,
    tuple,
    str,
    bytes,
    frozenset,
    io.IOBase,
    io.RawIOBase,
    io.BufferedIOBase,
    io.TextIOBase,
)
_PYTHON_BUILTIN_METHODS: frozenset[str] = frozenset(
    name
    for cls in _BUILTIN_TYPES
    for name in dir(cls)
    if not name.startswith("_") and callable(getattr(cls, name, None))
)

# ---------------------------------------------------------------------------
# JS/TS builtins — static set (no runtime introspection available).
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# LangConstants — the single config object consumed by GraphTreeSitterParser.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LangConstants:
    """AST node types, builtins, and behaviour flags for one language."""

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
    super_prefixes: tuple[str, ...]
    has_decorator: bool
    has_with_statement: bool
    has_property: bool
    import_handler_factory: Callable[[], object]


# ---------------------------------------------------------------------------
# Registry — private builders, single public lookup.
# ---------------------------------------------------------------------------


def _python() -> LangConstants:
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
        import_handler_factory=PythonImportHandler,
    )


def _js_ts() -> LangConstants:
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
        import_handler_factory=JsTsImportHandler,
    )


def _go() -> LangConstants:
    from coderay.graph._handlers.lang.registry import get_import_handler

    return LangConstants(
        import_types=("import_declaration",),
        function_scope_types=("function_declaration", "method_declaration"),
        class_scope_types=(),
        extra_class_scope_types=(),
        call_types=("call_expression",),
        assignment_types=("assignment",),
        class_body_types=("block",),
        typed_param_types=("typed_parameter",),
        builtins=frozenset(),
        self_prefixes=(),
        super_prefixes=(),
        has_decorator=False,
        has_with_statement=False,
        has_property=False,
        import_handler_factory=lambda: get_import_handler("go"),
    )


# lang_name → builder; called once per extract_graph_from_file invocation.
_BUILDERS: dict[str, Callable[[], LangConstants]] = {
    "python": _python,
    "javascript": _js_ts,
    "typescript": _js_ts,
    "go": _go,
}


def get_lang_constants(lang_name: str) -> LangConstants | None:
    """Return graph constants for *lang_name*, or None if unsupported."""
    builder = _BUILDERS.get(lang_name)
    return builder() if builder else None
