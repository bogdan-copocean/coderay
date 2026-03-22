from __future__ import annotations

import logging
import os
import platform
import sys

import numpy as np

from coderay.embedding.base import Embedder, EmbedTask
from coderay.embedding.local import MAX_CHARS
from coderay.embedding.prefixes import NOMIC_PREFIXES, is_nomic_model_id

logger = logging.getLogger(__name__)

_BATCH = int(os.environ.get("EMBED_BATCH_SIZE", 32))


def _require_apple_silicon() -> None:
    """Raise if MLX backend is not supported on this machine."""
    if sys.platform != "darwin":
        raise RuntimeError("MLX embedder is only supported on macOS.")
    if platform.machine().lower() != "arm64":
        raise RuntimeError("MLX embedder requires Apple Silicon (arm64).")


class MlxEmbedder(Embedder):
    """Apple Silicon embeddings via mlx-embeddings."""

    def __init__(
        self,
        model_id: str,
        dimensions: int,
        max_length: int = 2048,
    ) -> None:
        """Load MLX model id, output dimension, and tokenizer max_length."""
        _require_apple_silicon()
        self._model_id = model_id
        self._dimensions = dimensions
        self._max_length = max_length
        self._model = None
        self._tokenizer = None

    def _load(self) -> None:
        """Load model and tokenizer on first use."""
        try:
            from mlx_embeddings.utils import load as mlx_load
        except ImportError as e:
            raise RuntimeError(
                "MLX embedder requires mlx-embeddings; reinstall coderay."
            ) from e

        logger.info("Loading MLX embedding model %s...", self._model_id)
        self._model, self._tokenizer = mlx_load(self._model_id)

    @property
    def dimensions(self) -> int:
        """Return vector dimension."""
        return self._dimensions

    def _apply_nomic_prefix(self, texts: list[str], task: EmbedTask) -> list[str]:
        """Prepend Nomic search_document/search_query when model expects it."""
        if not is_nomic_model_id(self._model_id):
            return texts
        prefix = NOMIC_PREFIXES.get(task, "")
        if not prefix:
            return texts
        return [prefix + t for t in texts]

    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask = EmbedTask.DOCUMENT,
    ) -> list[list[float]]:
        """Embed texts; Nomic MLX models use asymmetric query/document prefixes."""
        if not texts:
            return []
        if self._model is None:
            self._load()
        assert self._model is not None and self._tokenizer is not None

        import mlx.core as mx

        truncated = [t[:MAX_CHARS] if len(t) > MAX_CHARS else t for t in texts]
        prefixed = self._apply_nomic_prefix(truncated, task)
        n_batches = (len(prefixed) + _BATCH - 1) // _BATCH
        logger.info(
            "Embedding %d chunks (mlx, batch_size=%d, max_length=%d, ~%d batches)...",
            len(prefixed),
            _BATCH,
            self._max_length,
            n_batches,
        )
        # mlx_embeddings.TokenizerWrapper is not callable; batch_encode_plus can
        # resolve to Rust TokenizersBackend (no batch_encode_plus in new transformers).
        tok = self._tokenizer
        if type(tok).__name__ == "TokenizerWrapper":
            tok = tok._tokenizer
        out: list[list[float]] = []
        for bi, i in enumerate(range(0, len(prefixed), _BATCH)):
            batch = prefixed[i : i + _BATCH]
            inputs = tok(
                batch,
                return_tensors="mlx",
                padding=True,
                truncation=True,
                max_length=self._max_length,
            )
            outputs = self._model(
                inputs["input_ids"],
                inputs["attention_mask"],
            )
            emb = outputs.text_embeds
            mx.eval(emb)
            arr = np.asarray(emb)
            for row in arr:
                out.append(row.astype(float).tolist())
            step = max(1, n_batches // 10)
            if bi == 0 or (bi + 1) % step == 0 or (bi + 1) == n_batches:
                logger.info("MLX embedding batch %d/%d", bi + 1, n_batches)

        if out and len(out[0]) != self._dimensions:
            raise RuntimeError(
                f"MLX model output dim {len(out[0])} != configured {self._dimensions}"
            )
        return out
