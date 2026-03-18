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
    from coderay.embedding.local import LocalEmbedder

    config = get_config()
    return LocalEmbedder(
        model=config.embedder.model,
        dimensions=config.embedder.dimensions,
    )
