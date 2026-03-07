"""Ollama embedder: local, no-API-key embeddings via Ollama's HTTP API."""

from __future__ import annotations

import logging
import os

from indexer.embedding.base import Embedder

logger = logging.getLogger(__name__)

MAX_CHARS_PER_TEXT = 8000


class OllamaEmbedder(Embedder):
    """Embeddings via a local Ollama server (e.g. nomic-embed-text).

    Requires Ollama running locally: https://ollama.com
    Pull a model first: ``ollama pull nomic-embed-text``
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        dimensions: int = 768,
        base_url: str = "http://localhost:11434",
    ) -> None:
        env_host = os.environ.get("OLLAMA_HOST")
        resolved = env_host or base_url
        self._model = model
        self._dimensions = dimensions
        self._base_url = resolved.rstrip("/")

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        import httpx

        truncated = [
            t[:MAX_CHARS_PER_TEXT] if len(t) > MAX_CHARS_PER_TEXT else t for t in texts
        ]

        url = f"{self._base_url}/api/embed"
        all_vectors: list[list[float]] = []
        for texts_batch in self._batch_by_char_budget(truncated, budget=24_000):
            vecs = self._embed_batch(url, texts_batch)
            all_vectors.extend(vecs)
        return all_vectors

    def _embed_batch(self, url: str, texts: list[str]) -> list[list[float]]:
        import httpx

        try:
            resp = httpx.post(
                url,
                json={"model": self._model, "input": texts},
                timeout=120.0,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if len(texts) == 1:
                logger.warning(
                    "Ollama: skipping 1 text (too long, %d chars)",
                    len(texts[0]),
                )
                return [[0.0] * self._dimensions]
            mid = len(texts) // 2
            left = self._embed_batch(url, texts[:mid])
            right = self._embed_batch(url, texts[mid:])
            return left + right
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.error("Ollama connection failed: %s", exc)
            raise RuntimeError(
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is Ollama running? Start with: ollama serve"
            ) from exc

        vecs: list[list[float]] = []
        for emb in resp.json().get("embeddings", []):
            if len(emb) != self._dimensions:
                emb = emb[: self._dimensions]
                emb.extend([0.0] * (self._dimensions - len(emb)))
            vecs.append(emb)
        return vecs

    @staticmethod
    def _batch_by_char_budget(
        texts: list[str], budget: int = 24_000
    ) -> list[list[str]]:
        """Split texts into batches that fit within a character budget."""
        batches: list[list[str]] = []
        current: list[str] = []
        current_len = 0
        for t in texts:
            tlen = len(t)
            if current and current_len + tlen > budget:
                batches.append(current)
                current = []
                current_len = 0
            current.append(t)
            current_len += tlen
        if current:
            batches.append(current)
        return batches
