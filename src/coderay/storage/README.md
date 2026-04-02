# storage

LanceDB-backed vector store for code chunks.

`Store` in `lancedb.py` handles insert, delete, vector search, hybrid search,
and maintenance. The `chunks` table schema:

| Field | Purpose |
|-------|---------|
| `path` | Repo-relative file path |
| `start_line` / `end_line` | Source location |
| `symbol` | Qualified symbol name |
| `content` | Raw source text of the chunk |
| `search_text` | `path + symbol + content` — used for BM25 full-text search |
| `vector` | Dense embedding |

## Hybrid search

`Store.search` combines cosine vector similarity with BM25 on `search_text`
using Reciprocal Rank Fusion (RRF). Controlled by `search.hybrid` in
`.coderay.toml`. Hybrid search improves recall for keyword-heavy queries
(identifiers, file names) without sacrificing semantic retrieval.

## Append-only model

Inserts create new fragments; deletes are logical (tombstones). This allows
fast incremental writes but accumulates space over time. Run
`coderay maintain` (or `Store.maintain()`) to compact fragments and reclaim
disk space.
