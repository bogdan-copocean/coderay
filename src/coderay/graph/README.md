# graph

Directed call/import/inheritance graph: parse → per-file `extract_facts` → merge [`CodeGraph`](code_graph.py) → [`run_post_merge_pipeline`](pipeline.py). Facts: [`facts.py`](facts.py); emit: [`emit.py`](emit.py).

**Public:** `extract_graph_from_file`, `build_graph`, `CodeGraph`, [`LanguageGraphPlugin`](plugin_protocol.py). **Internal:** [`plugins/lowering_common/`](plugins/lowering_common/), [`plugins/python/`](plugins/python/), [`plugins/js_ts/`](plugins/js_ts/).

`graph.json` carries `schema_version` ([`code_graph.py`](code_graph.py)); older indexes without it still load.

Tests: [`tests/graph/`](../tests/graph/).
