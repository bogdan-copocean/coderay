# retrieval

Search orchestration layer between the CLI/MCP and the vector store.

- `search.py` — `Retrieval` embeds the query, runs hybrid search
  (vector + BM25 FTS with RRF reranking) via LanceDB, then applies
  structural boosting.
- `boosting.py` — `StructuralBooster` adjusts search scores by file path
  (e.g. downrank `tests/`, boost `src/`). Rules are regex-based and
  configurable via `config.yaml`.
