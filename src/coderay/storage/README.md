# storage

LanceDB-backed vector store for code chunks.

`Store` in `lancedb.py` handles insert, delete, vector search, hybrid
search (BM25 + cosine via RRF), and maintenance (compact fragments,
clean old versions). The `chunks` table stores path, line range, symbol,
language, content, and embedding vector.

Append-only storage model: inserts create fragments, deletes are logical.
Run `maintain()` to reclaim space.
