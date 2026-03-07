"""Local embedder using fastembed (ONNX Runtime, no PyTorch).

Zero-config: works after ``pip install`` with no API key or external server.
Uses all-MiniLM-L6-v2 (384d, quantized ONNX, CPU-only).

fastembed is ~10x lighter than sentence-transformers because it skips PyTorch
entirely and talks to ONNX Runtime directly.
"""

from __future__ import annotations

import logging
import os

from indexer.embedding.base import Embedder

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DIMENSIONS = 384

# all-MiniLM-L6-v2 max_seq_length is 256 tokens (~1200 chars of code).
# Truncating early avoids the tokenizer wasting time on text the model
# will discard anyway.
#
# TODO: symbols exceeding this limit lose tail information. Future options:
#   - Split long chunks into overlapping windows and average embeddings
#   - Use a model with a larger context (e.g. nomic-embed-text, 8192 tokens)
#   - Embed a signature+docstring summary instead of raw code for large symbols
MAX_CHARS = 1500

# Number of parallel ONNX workers (0 = auto based on CPU cores)
_PARALLEL_WORKERS = int(os.environ.get("EMBED_WORKERS", 0)) or None


class LocalEmbedder(Embedder):
    """CPU-only embeddings via fastembed (ONNX Runtime)."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
    ) -> None:
        self._dimensions = dimensions
        self._model_name = model
        self._model = None

    def _load_model(self):
        from fastembed import TextEmbedding

        logger.info("Loading local embedding model %s...", self._model_name)
        self._model = TextEmbedding(model_name=self._model_name)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is None:
            self._load_model()

        truncated = [t[:MAX_CHARS] if len(t) > MAX_CHARS else t for t in texts]
        logger.info("Embedding %d chunks...", len(truncated))
        embeddings = list(
            self._model.embed(
                truncated,
                parallel=_PARALLEL_WORKERS,
                batch_size=256,
            )
        )
        return [e.tolist() for e in embeddings]
