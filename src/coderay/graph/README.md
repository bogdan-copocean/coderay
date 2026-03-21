# graph

Builds and queries a directed code relationship graph.

## Pipeline

1. **Parse** — Shared Tree-sitter driver ([`parsing/base.py`](../parsing/base.py)) produces a CST per file.
2. **Plugin** — Each language registers a [`LanguageGraphPlugin`](plugin_protocol.py): `extract_facts` (CST → facts), optional `resolve_facts`, then `emit` (facts → [`GraphNode`](../core/models.py) / [`GraphEdge`](../core/models.py)).
3. **Merge** — [`builder.py`](builder.py) merges per-file contributions into [`CodeGraph`](code_graph.py).
4. **Post-merge** — [`pipeline.py`](pipeline.py) runs global passes then language-specific passes (e.g. Python phantom rewrite/prune in [`plugins/python/passes.py`](plugins/python/passes.py)).

Facts are defined in [`facts.py`](facts.py); emission is centralized in [`emit.py`](emit.py).

## Persistence

`graph.json` includes `schema_version` (see `GRAPH_SCHEMA_VERSION` in [`code_graph.py`](code_graph.py)). Older indexes without the key still load.

## Tests

- [`tests/graph/handlers/`](../tests/graph/handlers/) — behavior per concern (imports, calls, definitions, etc.).
- [`tests/graph/test_emit_facts.py`](../tests/graph/test_emit_facts.py) — emit invariants.
- [`tests/graph/test_builder.py`](../tests/graph/test_builder.py) — integration and incremental updates.

## Known limitations

Same static-analysis limits as before (wildcard imports, higher-order calls, dynamic getattr, etc.).
