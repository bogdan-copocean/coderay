from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from coderay.core.config import Config

logger = logging.getLogger(__name__)


class Embedder(ABC):
    """Abstract embedder: embed(texts) -> list of vectors."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector dimension (e.g. 384 for all-MiniLM-L6-v2)."""
        ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts; returns one vector per text."""
        ...


def load_embedder_from_config(config: Config) -> Embedder:
    """Build an Embedder from a Config dataclass."""

    from coderay.embedding.local import LocalEmbedder

    return LocalEmbedder(
        model=config.embedder.model,
        dimensions=config.embedder.dimensions,
    )
