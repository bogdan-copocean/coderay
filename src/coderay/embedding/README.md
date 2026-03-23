# embedding

Maps code chunks to dense vectors.

## Backends

- **`LocalEmbedder`** — ONNX via fastembed. Default when `backend: fastembed` or `backend: auto` off Apple Silicon. Config: `embedder.fastembed`.
- **`MLXEmbedder`** — MLX on Apple Silicon. Default when `backend: mlx` or `backend: auto` on ARM Mac. Config: `embedder.mlx`.

`auto` resolves via `backend_resolve.resolved_embedder_backend()` — MLX when `mlx_embeddings` is importable, else fastembed.

Nomic models use asymmetric prefixes (`search_document:` / `search_query:`) — handled in `prefixes.py`.

`format_chunk_for_embedding()` in `format.py` defines how a chunk becomes an embedding input (path + symbol + content).
