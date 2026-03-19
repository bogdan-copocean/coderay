"""Python and JS/TS builtin names — used by graph config to filter noise edges.

Python builtins are introspected at import time so the sets stay current
with the interpreter version.  JS/TS builtins are a static set (no runtime
introspection available).
"""

from __future__ import annotations

import builtins
import io

# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

PYTHON_BUILTINS: frozenset[str] = frozenset(
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
PYTHON_BUILTIN_METHODS: frozenset[str] = frozenset(
    name
    for cls in _BUILTIN_TYPES
    for name in dir(cls)
    if not name.startswith("_") and callable(getattr(cls, name, None))
)

# Combined set: both module-level builtins and type method names.
PYTHON_ALL_BUILTINS: frozenset[str] = PYTHON_BUILTINS | PYTHON_BUILTIN_METHODS

# ---------------------------------------------------------------------------
# JS / TS
# ---------------------------------------------------------------------------

JS_TS_BUILTINS: frozenset[str] = frozenset(
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
