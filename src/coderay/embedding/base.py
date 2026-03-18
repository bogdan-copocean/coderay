from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


class EmbedTask(Enum):
    """Distinguish document-time vs. query-time embedding."""

    DOCUMENT = "document"
    QUERY = "query"


class Embedder(ABC):
    """Abstract embedder: embed(texts) -> list of vectors."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector dimension produced by this embedder."""
        ...

    @abstractmethod
    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask = EmbedTask.DOCUMENT,
    ) -> list[list[float]]:
        """Embed texts into vectors; one vector per input string."""
        ...


def load_embedder_from_config() -> Embedder:
    """Build an Embedder from the application config."""

    from coderay.core.config import get_config
    from coderay.embedding.local import LocalEmbedder

    config = get_config()
    return LocalEmbedder(
        model=config.embedder.model,
        dimensions=config.embedder.dimensions,
    )
