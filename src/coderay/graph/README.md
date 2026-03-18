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

When adding JS/TS or other language support to graph extraction: add one representative
test per new language per handler (or handler group), not full duplication of Python tests.

## Known limitations

- **Static analysis only** — `getattr`, `exec`, `eval`, metaclasses not tracked.
- **Wildcard imports** — `from X import *` not resolved; calls remain unresolved.
- **Higher-order callbacks** — `map(fn, items)` or untyped `def process(fn): fn()` not traced.
- **Dunder via builtins** — `len(obj)` → `obj.__len__`; changing `__len__` does not show `len()` callers.
- **Operator overloading** — `a + b` calls `__add__`; changing it does not show `+` callers.
- **Tuple unpacking** — `a, b = get_pair()`; `a()` when return type unknown leaves `a` unresolved.
- **Lambda/comprehension scope** — calls inside lambdas attributed to enclosing function.
- **super() with multiple inheritance** — only first base used; later base changes may not show.
- **Default argument evaluation** — `def f(x=expensive_init())` runs at definition time.
