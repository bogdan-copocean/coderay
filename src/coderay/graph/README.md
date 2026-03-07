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
