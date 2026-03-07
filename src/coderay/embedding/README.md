# embedding

Converts code chunks into dense vector embeddings.

Two providers behind a common `Embedder` interface:

- **Local** (default) — `all-MiniLM-L6-v2` via fastembed/ONNX Runtime, 384d.
  Offline, zero config. Truncates at 1500 chars (256-token model limit).
- **OpenAI** — `text-embedding-3-small`, 1536d. Requires `OPENAI_API_KEY`.
  Batches 100 texts per API call with exponential backoff on transient errors.

`load_embedder_from_config()` in `base.py` is the factory.
