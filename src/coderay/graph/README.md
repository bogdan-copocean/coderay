# graph

Directed call/import/inheritance graph over the indexed codebase.

## Pipeline

```
extract_graph_from_file()   # per file: CST → GraphFacts
    ↓
build_graph()               # merge all facts into CodeGraph
    ↓
run_post_merge_pipeline()   # resolve cross-file edges, prune phantoms
```

Facts (`facts.py`) capture nodes (functions, classes, modules) and edges
(CALLS, IMPORTS, INHERITS, CONTAINS). Emitting to the graph (`emit.py`)
adds real nodes and phantom nodes for unresolved call targets.

## CodeGraph (`code_graph.py`)

`CodeGraph` is a `networkx.DiGraph` with four indexes maintained in sync:

| Index | Key | Value |
|-------|-----|-------|
| `_symbol_index` | short name (`save`) | `{node IDs}` |
| `_qualified_index` | qualified name (`User.save`) | `{node IDs}` |
| `_file_index` | file path | `{node IDs}` |
| `_module_index` | dotted module name | node ID |

### Symbol resolution

`resolve_symbol(name)` — exact match → symbol index → qualified index.
Returns `None` if ambiguous.

`get_impact_radius(symbol)` layered resolution:
1. Exact via `resolve_symbol`
2. Fuzzy via `_fuzzy_resolve` (method-name match within the same file)
3. Disambiguation: if the name matches multiple nodes, returns a hint
   listing all candidates instead of silently returning not-found

### Blast radius BFS

`get_impact_radius` does a reverse BFS (predecessors) over
`CALLS | IMPORTS | INHERITS` edges up to `depth` hops. Seeds include
the resolved node plus the same method on parent classes (interface-aware).
Phantom alias nodes are seeded to catch callers that import via re-export
paths. Module nodes are suppressed when the file is already represented
by more specific function/class nodes.

## Language plugins

`plugins/python/` and `plugins/js_ts/` implement `LanguageGraphPlugin`.
`plugins/base/handlers/` contains shared call/import/class handlers.

## Persistence

Serialised to `graph.json` in the index directory. `schema_version` allows
forward-compatible loading of older indexes.
