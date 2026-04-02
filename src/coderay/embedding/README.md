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

## If indexing is slow

The default model (BGE Small, ~67MB via fastembed / ~25MB via MLX bf16) is a
good balance of speed and retrieval quality. If your repo is large and the first
build takes too long, consider a lighter model:

| Model | Backend | Size | Dimensions | Trade-off |
|-------|---------|------|------------|-----------|
| `BAAI/bge-small-en-v1.5` | fastembed | ~67MB | 384 | **Default.** Best retrieval quality in this size class. |
| `sentence-transformers/all-MiniLM-L6-v2` | fastembed | ~90MB | 384 | Widely used, slightly lower code retrieval quality than BGE Small. Larger download. |
| `mlx-community/bge-small-en-v1.5-4bit` | mlx | ~19MB | 384 | 4-bit quantised BGE Small. Fast on Apple Silicon, minimal download. Small quality delta vs bf16 — untested on code retrieval specifically. |
| `mlx-community/all-MiniLM-L6-v2-4bit` | mlx | ~13MB | 384 | Smallest option. Fastest cold start. Noticeably lower retrieval quality for code; best suited for quick experimentation. |

To switch, update `.coderay.toml` and run `coderay build --full`:

```toml
# Example: lighter MLX model on Apple Silicon
[embedder.mlx]
model_name = "mlx-community/bge-small-en-v1.5-4bit"
dimensions = 384
batch_size = 256
```

All models above use 384 dimensions, so switching between them only requires
`build --full` — no schema changes needed.
