# graph

Directed call/import/inheritance graph over the indexed codebase.

## Layout

| Area | Role |
|------|------|
| [`graph_builder.py`](graph_builder.py) | `GraphBuilder`: parse → extract facts → materialise → merge; optional `resolve_facts` hook; `include_external` filtering |
| [`builder.py`](builder.py) | `build_graph` / `build_and_save_graph` — module index + `GraphBuilder.build` + `save_graph` |
| [`extractors/`](extractors/) | `BaseGraphExtractor` + per-language extractors (Python, JS/TS); `build_module_index` and `extract_graph_from_file` live here |
| [`handlers/`](handlers/) | Shared handlers (`definition`, `call`, `assignment`, `decorator`, …) |
| [`handlers/<lang>/`](handlers/python/) | Language-specific handlers (imports, assignments, definitions) |
| [`lowering/`](lowering/) | `LoweringSession`, `FileNameBindings`, `CalleeResolver` — CST helpers for handlers |
| [`passes/`](passes/) | Post-merge global passes; Python-only steps in [`passes/python.py`](passes/python.py) |
| [`pipeline.py`](pipeline.py) | `run_post_merge_pipeline` — Python passes + `run_global_passes` |
| [`impact.py`](impact.py) | `get_impact_radius` — reverse BFS over the graph |
| [`materialise.py`](materialise.py) | Turns facts into `GraphNode` / `GraphEdge` (including phantom targets for unresolved calls) |
| [`facts.py`](facts.py) | `NodeFact`, `EdgeFact` — the intermediate representation emitted by extractors |
| [`language_plugin.py`](language_plugin.py) | `LanguagePlugin` protocol — the interface each language extractor implements |

## Pipeline

```
GraphBuilder.process_file() / extract_graph_from_file()   # CST → facts → materialise
    ↓
build_graph()                    # merge all files → CodeGraph
    ↓
run_post_merge_pipeline()        # cross-file passes, prune phantoms
```

`GraphBuilder` selects the extractor from `lang_cfg.name` (`python` | `javascript` | `typescript`). Facts (`facts.py`) describe nodes and edges; [`materialise.py`](materialise.py) turns facts into `GraphNode` / `GraphEdge` (including phantom targets for unresolved calls).

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

## Language modules

[`extractors/python/`](extractors/python/) and [`extractors/js_ts/`](extractors/js_ts/)
hold extractors; language-specific handlers (imports, typing, assignments) sit under
[`handlers/python/`](handlers/python/) and [`handlers/js_ts/`](handlers/js_ts/).

## Persistence

Serialised to `graph.json` in the index directory. `schema_version` allows
forward-compatible loading of older indexes.
