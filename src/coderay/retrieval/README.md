# retrieval

Search orchestration between the CLI/MCP and the vector store.

- `search.py` — `Retrieval` embeds the query (with `EmbedTask.QUERY` for asymmetric models), calls `Store.search` (hybrid when `semantic_search.hybrid` is true: vector + BM25 on `search_text` with RRF reranking), then structural boosting.
- `boosting.py` — `StructuralBooster` adjusts scores by file path (e.g. downrank `tests/`, boost `src/`). Rules are regex-based and configurable via `config.yaml`.

Hybrid search uses a combined lexical field (`path`, `symbol`, `content`) so keyword-style queries (e.g. library or file names) surface alongside dense similarity.
