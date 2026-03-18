from __future__ import annotations

import logging
import os

from coderay.embedding.base import Embedder, EmbedTask

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "nomic-ai/nomic-embed-text-v1.5"
DEFAULT_DIMENSIONS = 768

# nomic-embed-text-v1.5 supports 8192 tokens.  Code averages roughly
# 1.5 characters per token, giving ~12 000 usable characters.  Truncating
# early avoids the tokenizer wasting time on text the model will discard.
MAX_CHARS = 12_000

# Number of parallel ONNX workers (0 = auto based on CPU cores)
_PARALLEL_WORKERS = int(os.environ.get("EMBED_WORKERS", 0)) or None

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
    """CPU-only embeddings via fastembed (ONNX Runtime)."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
    ) -> None:
        """Initialize with model name and vector dimensions."""
        self._dimensions = dimensions
        self._model_name = model
        self._model = None

    def _load_model(self):
        """Lazily load the fastembed model on first use."""
        from fastembed import TextEmbedding

        logger.info("Loading local embedding model %s...", self._model_name)
        self._model = TextEmbedding(model_name=self._model_name)

    @property
    def dimensions(self) -> int:
        """Vector dimension (e.g. 768 for nomic-embed-text-v1.5)."""
        return self._dimensions

    def _apply_prefix(self, texts: list[str], task: EmbedTask) -> list[str]:
        """Prepend model-specific task prefix when available."""
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
        """Embed texts using fastembed; returns one vector per text.

        Args:
            texts: Raw text strings to embed.
            task: Whether these are documents or queries; controls
                which instruction prefix (if any) is prepended.
        """
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
                batch_size=256,
            )
        )
        return [e.tolist() for e in embeddings]
