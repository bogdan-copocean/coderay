# embedding

Converts code chunks into dense vector embeddings.

`LocalEmbedder` (default) — `all-MiniLM-L6-v2` via fastembed/ONNX Runtime, 384d.
Offline, zero config. Truncates at 1500 chars (256-token model limit).

`load_embedder_from_config()` in `base.py` is the factory.
