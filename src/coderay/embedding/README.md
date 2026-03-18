# embedding

Converts code chunks into dense vector embeddings.

`LocalEmbedder` (default) — `all-MiniLM-L6-v2` via fastembed/ONNX Runtime, 384d.
Offline-first, zero config. Truncates at 384 chars (256-token model limit).

`load_embedder_from_config()` in `base.py` is the factory.
