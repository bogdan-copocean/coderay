from __future__ import annotations

import logging
import os

from onnxruntime.capi.onnxruntime_pybind11_state import NoSuchFile

from coderay.embedding.base import Embedder, EmbedTask
from coderay.embedding.prefixes import NOMIC_PREFIXES

logger = logging.getLogger(__name__)

# Nomic v1.5 supports ~8192 tokens; cap raw chars to bound memory (tokenizer truncates).
_DEFAULT_MAX_CHARS = 120_000

# Number of parallel ONNX workers (0 = auto based on CPU cores)
_PARALLEL_WORKERS = int(os.environ.get("EMBED_WORKERS", 0)) or None

# Batch size for embedding; lower if OOM (e.g. EMBED_BATCH_SIZE=32)
_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", 64))

_MAX_CHARS = int(os.environ.get("EMBED_MAX_CHARS", _DEFAULT_MAX_CHARS))

# Tests and tooling may reference the active char cap.
MAX_CHARS = _MAX_CHARS

# Model-specific task prefixes for asymmetric retrieval.
_TASK_PREFIXES: dict[str, dict[EmbedTask, str]] = {
    "nomic-ai/nomic-embed-text-v1.5": NOMIC_PREFIXES,
    "nomic-ai/nomic-embed-text-v1.5-Q": NOMIC_PREFIXES,
}


class LocalEmbedder(Embedder):
    """CPU embeddings via fastembed."""

    def __init__(
        self,
        model: str,
        dimensions: int,
    ) -> None:
        """Initialize with model name and dimensions."""
        self._dimensions = dimensions
        self._model_name = model
        self._model = None

    @property
    def dimensions(self) -> int:
        """Return vector dimension."""
        return self._dimensions

    def _load_model(self):
        """Load fastembed model on first use; try cache then download."""
        from fastembed import TextEmbedding

        def _open(name: str, local_only: bool) -> object:
            return TextEmbedding(model_name=name, local_files_only=local_only)

        logger.info("Loading local embedding model %s...", self._model_name)
        try:
            self._model = _open(name=self._model_name, local_only=True)
        except (NoSuchFile, ValueError) as e:
            if isinstance(e, ValueError) and "Could not load model" not in str(e):
                raise
            logger.info("Model not cached, downloading (one-time)...")
            self._model = _open(name=self._model_name, local_only=False)

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

        truncated = [t[:_MAX_CHARS] if len(t) > _MAX_CHARS else t for t in texts]
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
