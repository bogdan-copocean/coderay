"""
Configurable embedder abstraction.
Local (fastembed/ONNX), Ollama, and OpenAI implementations;
interface allows adding other providers.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from indexer.core.config import get_embedding_dimensions

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
    """Build an Embedder from a config dict.

    Supports providers: "local" (default), "ollama", "openai".
    """
    emb = config.get("embedder") or {}
    provider = (emb.get("provider") or "local").lower()

    if provider == "local":
        try:
            from indexer.embedding.local import LocalEmbedder
        except ImportError as exc:
            raise ImportError(
                "Local provider requires 'fastembed'. "
                "Install with: pip install semantic-code-indexer"
            ) from exc
        return LocalEmbedder(
            model=emb.get("model") or "sentence-transformers/all-MiniLM-L6-v2",
            dimensions=get_embedding_dimensions(config),
        )

    if provider == "openai":
        try:
            from indexer.embedding.openai import OpenAIEmbedder
        except ImportError as exc:
            raise ImportError(
                "OpenAI provider requires the 'openai' package. "
                "Install with: pip install source-code-indexer[openai]"
            ) from exc
        return OpenAIEmbedder(
            model=emb.get("model") or "text-embedding-3-small",
            dimensions=get_embedding_dimensions(config),
            api_key=emb.get("api_key"),
        )

    if provider == "ollama":
        from indexer.embedding.ollama import OllamaEmbedder

        return OllamaEmbedder(
            model=emb.get("model") or "nomic-embed-text",
            base_url=emb.get("base_url") or "http://localhost:11434",
            dimensions=get_embedding_dimensions(config),
        )

    raise ValueError(
        f"Unknown embedder provider: {provider}. "
        "Supported: 'local', 'openai', 'ollama'."
    )
