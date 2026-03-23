# embedding

Maps code chunks to dense vectors.

## Backends

- **`LocalEmbedder`** — ONNX via fastembed when the resolved backend is **`fastembed`** (including **`backend: auto`** off Apple Silicon or without `mlx-embeddings`). Defaults: **`nomic-ai/nomic-embed-text-v1.5`** (768d). Config: `embedder.fastembed`. **`v1.5-Q`**: if quantized ONNX is missing, we fall back to full **v1.5**.
- **`MLXEmbedder`** — when **`backend: mlx`** or **`backend: auto`** on Apple Silicon (MLX packages are default dependencies there). Defaults: **`mlx-community/nomicai-modernbert-embed-base-4bit`** (768d). Config: `embedder.mlx`.

Nomic models use **asymmetric** prefixes (`search_document:` / `search_query:`) — see `prefixes.py` and `LocalEmbedder` / `MLXEmbedder`.

- **`format_chunk_for_embedding()`** — combines `path`, `symbol`, and `content` for document embedding.

`load_embedder_from_config()` in `base.py` uses **`backend_resolve.resolved_embedder_backend()`** ( **`auto`** → MLX on Apple Silicon when `mlx_embeddings` imports, else fastembed).

## Glossary

- **Tensor**: here, a **multidimensional array of numbers** (the framework’s array type: MLX arrays, NumPy arrays, etc.). Embeddings are vectors (1D tensors).
- **Padding** (batch tokenization): sequences in a batch are **different lengths** after tokenization. **Padding** inserts extra **special pad token IDs** at the end of shorter sequences so every row has the same length for one batched matrix multiply. The **attention mask** marks real tokens vs pads so the model does not treat pads as content. This is **not** “zero vectors” in the final embedding space — those are token IDs along the sequence dimension before the model produces one vector per input text.
