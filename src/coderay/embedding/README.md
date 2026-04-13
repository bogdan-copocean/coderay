# embedding

Maps code chunks to dense vectors for storage and query.

## Backends

- **`LocalEmbedder`** (`local.py`) — ONNX via fastembed. Default on all
  platforms and on Apple Silicon when `coderay[mlx]` is not installed.
  Configured via `[embedder.fastembed]`.
- **`MLXEmbedder`** (`mlx_backend.py`) — Metal-accelerated on Apple Silicon.
  Requires `pip install coderay[mlx]`. Configured via `[embedder.mlx]`.

`backend: auto` (default) resolves via `backend_resolve.py`: picks MLX when
`mlx_embeddings` is importable, else fastembed.

## Key files

- `base.py` — `Embedder` protocol and `EmbedTask` enum (`DOCUMENT` / `QUERY`).
- `format.py` — `format_chunk_for_embedding()`: serialises a chunk as
  `path + symbol + content` so identifiers and paths influence retrieval
  alongside semantic meaning.
- `prefixes.py` — `requires_prefix()`: detects models that need asymmetric
  `search_document:` / `search_query:` prefixes (e.g. E5 family).

## Changing backends or models

Run `coderay build --full` after any change to `[embedder]` config. Vectors
from different models are not compatible.

## Defaults and trade-offs

The default is **MiniLM L6** (`sentence-transformers/all-MiniLM-L6-v2` on CPU,
`mlx-community/all-MiniLM-L6-v2-bf16` on MLX): fast indexing and good enough
semantic search for most workflows. For **stronger embeddings** (often better
retrieval on code), switch to **BGE Small** — expect a heavier download and more
compute than MiniLM.

| Model | Backend | Size (approx.) | Dimensions | Notes |
|-------|---------|----------------|------------|-------|
| `sentence-transformers/all-MiniLM-L6-v2` | fastembed | ~90MB | 384 | **Default.** Fast; widely used. |
| `BAAI/bge-small-en-v1.5` | fastembed | ~67MB | 384 | Heavier quality focus; strong retrieval in this size class. |
| `mlx-community/all-MiniLM-L6-v2-bf16` | mlx | ~45MB | 384 | **Default** on Apple Silicon with `coderay[mlx]`. |
| `mlx-community/bge-small-en-v1.5-bf16` | mlx | ~25MB | 384 | BGE on MLX; better embeddings than MiniLM, more work per batch. |
| `mlx-community/bge-small-en-v1.5-4bit` | mlx | ~19MB | 384 | 4-bit BGE; smaller download, small quality delta vs bf16. |
| `mlx-community/all-MiniLM-L6-v2-4bit` | mlx | ~13MB | 384 | Smallest; fastest cold start; lower retrieval quality for code. |

To use BGE instead of the defaults, edit `.coderay.toml` and run `coderay build --full`:

```toml
[embedder.fastembed]
model_name = "BAAI/bge-small-en-v1.5"
dimensions = 384
batch_size = 64

[embedder.mlx]
model_name = "mlx-community/bge-small-en-v1.5-bf16"
dimensions = 384
batch_size = 256
```

All models above use 384 dimensions, so switching between them only requires
`build --full` — no schema changes needed.
