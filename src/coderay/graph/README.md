# graph

Builds and queries a directed code relationship graph.

## How it works

1. `extractor.py` walks tree-sitter syntax trees to produce nodes (modules,
   functions, classes) and edges (IMPORTS, DEFINES, CALLS, INHERITS).
   Built-in callee names are filtered out to reduce noise.
2. `code_graph.py` wraps a NetworkX DiGraph with three secondary indexes
   (symbol, module, file) for O(1) lookups. `resolve_edges()` rewires
   bare call targets to fully-qualified node IDs. `get_impact_radius()`
   performs reverse BFS to find the blast radius of a change.
3. `builder.py` orchestrates extraction and persistence (graph.json).
   Supports incremental updates by removing changed files before re-extraction.

## Tests

Handler-specific tests live in `tests/graph/handlers/`, one file per mixin:

- `test_imports.py` — ImportHandlerMixin: bare/from/aliased imports, relative paths
- `test_definitions.py` — DefinitionHandlerMixin: DEFINES, INHERITS, @property, typed params
- `test_calls.py` — CallHandlerMixin: resolution (self, super, chains), filtering, decorators
- `test_assignments.py` — AssignmentHandlerMixin: aliases, injection, with-statement, unpacking
- `test_type_resolution.py` — TypeResolutionMixin: union, Self, factory/param/property types

`test_extractor.py` covers FileContext, build_module_filter, and minimal integration.
`test_extractor_playground.py` runs full graph_sample smoke tests and known-gap xfails.

## Known limitations

- **Static analysis only** — dynamic dispatch (`getattr`, `exec`, `eval`,
  metaclasses) is not tracked.
- **Wildcard imports** — `from X import *` is not resolved. Names imported
  via wildcard are not registered; calls to them remain unresolved.
- **Higher-order callbacks** — calls through parameters (e.g. `map(fn, items)`)
  or untyped callable params (e.g. `def process(fn): fn()`) are not traced
  across function boundaries.
- **Dunder methods via builtins** — `len(obj)` → `obj.__len__`, `iter(x)` →
  `x.__iter__`. Changing `MyClass.__len__` does not show callers of
  `len(my_instance)`.
- **Operator overloading** — `a + b` calls `__add__` / `__radd__`. Changing
  these methods does not show callers of `a + b`.
- **Tuple unpacking without type hints** — `a, b = get_pair()`; `a()` when
  return type is unknown leaves `a` unresolved. Changing the returned callable
  does not show callers.
- **Lambda/comprehension scope** — calls inside lambdas (e.g. `abs(x)` in
  `map(lambda x: abs(x), items)`) are attributed to the enclosing function,
  not the lambda. Impact radius for "who calls abs?" is correct; "what calls
  this lambda?" has no node.
- **super() with multiple inheritance** — only the first base class is used.
  Changing a later base's method may not show the subclass as impacted.
- **Default argument evaluation** — `def f(x=expensive_init()):` runs at
  definition time; attribution may be to module scope.
