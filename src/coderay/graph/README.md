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

## Known limitations

- **Static analysis only** — dynamic dispatch (`getattr`, `exec`, `eval`,
  metaclasses) is not tracked.
- **Wildcard imports** — `from X import *` requires the target module to be
  indexed and uses `__all__` or public names when available.
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
