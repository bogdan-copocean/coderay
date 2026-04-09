from __future__ import annotations

import logging
from typing import Any

from onnxruntime.capi.onnxruntime_pybind11_state import NoSuchFile

from coderay.core.timing import timed_phase
from coderay.embedding.base import Embedder, EmbedTask
from coderay.embedding.prefixes import SEARCH_PREFIXES, requires_prefix

logger = logging.getLogger(__name__)


class LocalEmbedder(Embedder):
    """CPU embeddings via fastembed."""

    def __init__(
        self,
        model: str,
        dimensions: int,
        matryoshka_dimensions: int | None = None,
        batch_size: int = 64,
    ) -> None:
        self._model_name = model
        self._dimensions = dimensions
        self._matryoshka_dimensions = matryoshka_dimensions
        self._batch_size = batch_size
        self._model: Any = None

    @property
    def dimensions(self) -> int:
        return self._matryoshka_dimensions or self._dimensions

    def _load_model(self) -> None:
        from fastembed import TextEmbedding

        def _open(name: str, local_only: bool) -> TextEmbedding:
            return TextEmbedding(model_name=name, local_files_only=local_only)

        try:
            self._model = _open(name=self._model_name, local_only=True)
        except (NoSuchFile, ValueError) as e:
            if isinstance(e, ValueError) and "Could not load model" not in str(e):
                raise
            self._model = _open(name=self._model_name, local_only=False)
            logger.info("Model %s ready (downloaded).", self._model_name)
        else:
            logger.info("Model %s ready (cache).", self._model_name)

    def _apply_prefix(self, texts: list[str], task: EmbedTask) -> list[str]:
        if not requires_prefix(self._model_name):
            return texts
        prefix = SEARCH_PREFIXES.get(task, "")
        return [prefix + t for t in texts] if prefix else texts

    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask = EmbedTask.DOCUMENT,
    ) -> list[list[float]]:
        if not texts:
            return []
        if self._model is None:
            self._load_model()

        prefixed = self._apply_prefix(texts, task)
        n = len(prefixed)
        logger.info("Embedding %d chunks (task=%s)...", n, task.value)
        raw: list[Any] = []
        bs = self._batch_size
        with timed_phase("embedding", log=False) as tp:
            for i in range(0, n, bs):
                sub = prefixed[i : i + bs]
                part = list(self._model.embed(sub, batch_size=self._batch_size))
                raw.extend(part)
                logger.info("Embedded %d/%d chunks", min(i + len(sub), n), n)
        logger.info(
            "Embedding complete: %d chunks in %.2fs",
            n,
            tp.elapsed,
        )
        if self._matryoshka_dimensions is not None:
            return [e.tolist()[: self._matryoshka_dimensions] for e in raw]
        return [e.tolist() for e in raw]
