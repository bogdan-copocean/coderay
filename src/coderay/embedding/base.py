from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


class EmbedTask(Enum):
    """Distinguishes document-time vs. query-time embedding.

    Modern retrieval models produce better results when the text is
    prefixed with a task hint (e.g. ``search_document:`` vs.
    ``search_query:``).  Passing the correct task allows the embedder
    to apply the right prefix automatically.
    """

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
        """Embed a list of texts; returns one vector per text.

        Args:
            texts: Raw text strings to embed.
            task: Whether these texts are documents being indexed or
                queries being searched.  The embedder may prepend a
                model-specific instruction prefix based on this value.
        """
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
