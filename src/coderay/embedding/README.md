# embedding

Maps code chunks to dense vectors.

## Backends

- **`LocalEmbedder`** — ONNX via fastembed. Default when `backend: fastembed` or `backend: auto` off Apple Silicon. Config: `embedder.fastembed`.
- **`MLXEmbedder`** — MLX on Apple Silicon when optional `pip install coderay[mlx]` is used. Config: `embedder.mlx`.

`auto` resolves via `backend_resolve.resolved_embedder_backend()` — MLX when `mlx_embeddings` is importable, else fastembed.

Models that require asymmetric prefixes (`search_document:` / `search_query:`) are detected by `requires_prefix()` in `prefixes.py`.

`format_chunk_for_embedding()` in `format.py` defines how a chunk becomes an embedding input (path + symbol + content).
