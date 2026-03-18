from __future__ import annotations

import logging
import os

from coderay.embedding.base import Embedder, EmbedTask

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DIMENSIONS = 384

# all-MiniLM-L6-v2 supports 256 tokens (~384 chars). Truncate early to avoid waste.
MAX_CHARS = 384

# Number of parallel ONNX workers (0 = auto based on CPU cores)
_PARALLEL_WORKERS = int(os.environ.get("EMBED_WORKERS", 0)) or None

# Batch size for embedding; lower if OOM (e.g. EMBED_BATCH_SIZE=32)
_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", 64))

# Model-specific task prefixes for asymmetric retrieval.
# Models not listed here get no prefix (symmetric embedding).
_TASK_PREFIXES: dict[str, dict[EmbedTask, str]] = {
    "nomic-ai/nomic-embed-text-v1.5": {
        EmbedTask.DOCUMENT: "search_document: ",
        EmbedTask.QUERY: "search_query: ",
    },
    "nomic-ai/nomic-embed-text-v1.5-Q": {
        EmbedTask.DOCUMENT: "search_document: ",
        EmbedTask.QUERY: "search_query: ",
    },
}


class LocalEmbedder(Embedder):
    """CPU embeddings via fastembed."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
    ) -> None:
        """Initialize with model name and dimensions."""
        self._dimensions = dimensions
        self._model_name = model
        self._model = None

    def _load_model(self):
        """Load fastembed model on first use; try cache then download."""
        from fastembed import TextEmbedding

        logger.info("Loading local embedding model %s...", self._model_name)
        try:
            self._model = TextEmbedding(
                model_name=self._model_name,
                local_files_only=True,
            )
        except ValueError as e:
            if "Could not load model" in str(e):
                logger.info("Model not cached, downloading (one-time)...")
                self._model = TextEmbedding(
                    model_name=self._model_name,
                    local_files_only=False,
                )
            else:
                raise

    @property
    def dimensions(self) -> int:
        """Return vector dimension."""
        return self._dimensions

    def _apply_prefix(self, texts: list[str], task: EmbedTask) -> list[str]:
        """Prepend task prefix when available."""
        prefixes = _TASK_PREFIXES.get(self._model_name)
        if prefixes is None:
            return texts
        prefix = prefixes.get(task, "")
        if not prefix:
            return texts
        return [prefix + t for t in texts]

    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask = EmbedTask.DOCUMENT,
    ) -> list[list[float]]:
        """Embed texts via fastembed."""
        if not texts:
            return []
        if self._model is None:
            self._load_model()

        truncated = [t[:MAX_CHARS] if len(t) > MAX_CHARS else t for t in texts]
        prefixed = self._apply_prefix(truncated, task)

        logger.info("Embedding %d chunks (task=%s)...", len(prefixed), task.value)
        embeddings = list(
            self._model.embed(
                prefixed,
                parallel=_PARALLEL_WORKERS,
                batch_size=_BATCH_SIZE,
            )
        )
        return [e.tolist() for e in embeddings]
