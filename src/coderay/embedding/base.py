from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from coderay.core.config import get_embedding_dimensions

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


def load_embedder_from_config(config: dict[str, Any]) -> Embedder:
    """Build an Embedder from a config dict."""
    emb = config.get("embedder") or {}

    from coderay.embedding.local import LocalEmbedder

    return LocalEmbedder(
        model=emb.get("model"),
        dimensions=get_embedding_dimensions(config),
    )
