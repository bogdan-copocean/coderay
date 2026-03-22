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
    from coderay.embedding.backend_resolve import resolved_embedder_backend
    from coderay.embedding.local import LocalEmbedder
    from coderay.embedding.mlx_backend import MlxEmbedder

    config = get_config()
    ed = config.embedder
    backend = resolved_embedder_backend(ed.backend)
    if (ed.backend or "auto").strip().lower() == "auto":
        logger.info("embedder.backend=auto -> %s", backend)
    if backend == "mlx":
        mx = ed.mlx
        return MlxEmbedder(
            model_id=mx.model,
            dimensions=mx.dimensions,
            max_length=mx.max_length,
        )
    fe = ed.fastembed
    return LocalEmbedder(
        model=fe.model,
        dimensions=fe.dimensions,
    )
