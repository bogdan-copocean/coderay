import logging

from coderay.embedding.base import Embedder, EmbedTask
from coderay.embedding.prefixes import SEARCH_PREFIXES, requires_prefix

logger = logging.getLogger(__name__)


class MLXEmbedder(Embedder):
    def __init__(
        self,
        model_name: str,
        *,
        dimensions: int,
        matryoshka_dimensions: int | None = None,
        batch_size: int = 256,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._matryoshka_dimensions = matryoshka_dimensions
        self._batch_size = batch_size
        self._model = None
        self._tokenizer = None

    @property
    def dimensions(self) -> int:
        return self._matryoshka_dimensions or self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask = EmbedTask.DOCUMENT,
    ) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_loaded()

        if requires_prefix(self._model_name):
            prefix = SEARCH_PREFIXES.get(task, "")
            texts = [prefix + t for t in texts] if prefix else texts

        return self._embed_batched(texts)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import mlx.core as mx
        from mlx_embeddings import load

        cached = self._is_cached()
        if cached:
            logger.info(
                "Loading model %s from cache (%s)...",
                self._model_name,
                mx.default_device(),
            )
        else:
            logger.info(
                "Downloading model %s (one-time, %s)...",
                self._model_name,
                mx.default_device(),
            )
        self._model, self._tokenizer = load(self._model_name)
        logger.info("Model %s ready.", self._model_name)

    def _is_cached(self) -> bool:
        """Check if model exists in huggingface cache."""
        try:
            from huggingface_hub import try_to_load_from_cache

            result = try_to_load_from_cache(self._model_name, "config.json")
            return result is not None and isinstance(result, str)
        except Exception:
            return False

    def _embed_batched(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        n = len(texts)
        bs = self._batch_size

        for i in range(0, n, bs):
            batch = texts[i : i + bs]
            arr = self._embed_single_batch(batch)
            out.extend(arr.tolist())
            logger.info("MLX embedded %d/%d", min(i + bs, n), n)

        return out

    def _embed_single_batch(self, batch: list[str]):
        import numpy as np
        from mlx_embeddings import generate

        output = generate(self._model, self._tokenizer, batch)
        arr = np.asarray(output.text_embeds, dtype=np.float32)

        if arr.shape[1] != self._dimensions:
            raise RuntimeError(
                f"Model output {arr.shape[1]}d != configured {self._dimensions}d"
            )
        if self._matryoshka_dimensions is not None:
            arr = arr[:, : self._matryoshka_dimensions]
        return arr
