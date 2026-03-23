import logging

from coderay.embedding.base import EmbedTask

logger = logging.getLogger(__name__)

_BATCH = 256

_TASK_PREFIXES: dict[str, dict[EmbedTask, str]] = {
    "nomic": {
        EmbedTask.DOCUMENT: "search_document: ",
        EmbedTask.QUERY: "search_query: ",
    },
    "modernbert": {
        EmbedTask.DOCUMENT: "search_document: ",
        EmbedTask.QUERY: "search_query: ",
    },
}

_NO_PREFIX = {
    EmbedTask.DOCUMENT: "",
    EmbedTask.QUERY: "",
}


class MlxEmbedder:
    def __init__(
        self,
        model_name: str,
        *,
        dimensions: int,
        batch_size: int = _BATCH,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._model = None
        self._tokenizer = None
        self._prefixes = self._resolve_prefixes(model_name)

    @property
    def dimensions(self) -> int:
        return self._dimensions

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

        prefix = self._prefixes[task]
        prefixed = [prefix + t for t in texts] if prefix else texts

        return self._embed_batched(prefixed)

    @staticmethod
    def _resolve_prefixes(model_name: str) -> dict[EmbedTask, str]:
        """
        Resolve task prefixes based on model family name.
        Extend _TASK_PREFIXES dict to support new model families
        without touching this method.
        """
        lower = model_name.lower()
        for family, prefixes in _TASK_PREFIXES.items():
            if family in lower:
                return prefixes
        return _NO_PREFIX

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import mlx.core as mx
        from mlx_embeddings import load

        logger.info(
            "Loading MLX model %s on %s...", self._model_name, mx.default_device()
        )
        self._model, self._tokenizer = load(self._model_name)
        logger.info("MLX model ready.")

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

        if arr.shape[1] > self._dimensions:
            arr = arr[:, : self._dimensions]
        elif arr.shape[1] != self._dimensions:
            raise RuntimeError(
                f"Model output {arr.shape[1]}d != configured {self._dimensions}d"
            )
        return arr
