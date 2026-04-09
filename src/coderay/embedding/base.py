from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


class EmbedTask(Enum):
    """Document vs query embedding."""

    DOCUMENT = "document"
    QUERY = "query"


class Embedder(ABC):
    """Abstract embedder: embed(texts) -> vectors."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return vector dimension."""
        ...

    @abstractmethod
    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask = EmbedTask.DOCUMENT,
    ) -> list[list[float]]:
        """Embed texts into vectors."""
        ...


def load_embedder_from_config() -> Embedder:
    """Build Embedder from application config."""

    from coderay.core.config import get_config
    from coderay.embedding.backend_resolve import (
        mlx_optional_installed,
        resolved_embedder_backend,
    )
    from coderay.embedding.local import LocalEmbedder
    from coderay.embedding.mlx_backend import MLXEmbedder

    config = get_config()
    ed = config.embedder
    backend = resolved_embedder_backend(ed.backend)
    if backend == "mlx" and not mlx_optional_installed():
        raise RuntimeError(
            "embedder.backend is 'mlx' but MLX is not installed. "
            "On Apple Silicon: pip install 'coderay[mlx]'"
        )
    model_name = ed.mlx.model_name if backend == "mlx" else ed.fastembed.model_name
    logger.info("embedder.backend=%s model=%s", backend, model_name)
    if backend == "mlx":
        mx = ed.mlx
        return MLXEmbedder(
            model_name=mx.model_name,
            dimensions=mx.dimensions,
            matryoshka_dimensions=mx.matryoshka_dimensions,
            batch_size=mx.batch_size,
        )
    fe = ed.fastembed
    return LocalEmbedder(
        model=fe.model_name,
        dimensions=fe.dimensions,
        matryoshka_dimensions=fe.matryoshka_dimensions,
        batch_size=fe.batch_size,
    )
