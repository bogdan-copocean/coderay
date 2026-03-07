"""OpenAI embedder implementation."""

from __future__ import annotations

import logging
import time

from indexer.embedding.base import Embedder

logger = logging.getLogger(__name__)

MAX_CHARS_PER_TEXT = 8000
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


class OpenAIEmbedder(Embedder):
    """OpenAI embeddings (e.g. text-embedding-3-small).

    API key from env OPENAI_API_KEY or config.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        api_key: str | None = None,
    ):
        import os

        import openai

        self._model = model
        self._dimensions = dimensions
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenAI API key required: set OPENAI_API_KEY or pass api_key"
            )
        self._client = openai.OpenAI(api_key=self._api_key)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        truncated = [
            t[:MAX_CHARS_PER_TEXT] if len(t) > MAX_CHARS_PER_TEXT else t for t in texts
        ]

        batch_size = 100
        all_vectors: list[list[float]] = []
        for i in range(0, len(truncated), batch_size):
            batch = truncated[i : i + batch_size]
            vecs = self._embed_with_retry(batch)
            all_vectors.extend(vecs)
        return all_vectors

    def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        import openai

        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                    dimensions=self._dimensions,
                )
                return [e.embedding for e in resp.data]
            except (
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.InternalServerError,
            ) as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "OpenAI embed attempt %d failed (%s), retrying in %.1fs...",
                    attempt + 1,
                    exc,
                    delay,
                )
                time.sleep(delay)
        return []
