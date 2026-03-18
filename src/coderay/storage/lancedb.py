from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any

import lancedb
from lancedb.rerankers import RRFReranker

from coderay.core.config import get_config
from coderay.core.errors import EmbeddingDimensionError, ScoreExtractionError
from coderay.core.models import Chunk

logger = logging.getLogger(__name__)

TABLE_NAME = "chunks"

_RERANKER = RRFReranker()

_HYBRID_FAILURE_WARN_THRESHOLD = 3


class _ScoreField(Enum):
    """Known LanceDB score column names, keyed by search mode."""

    RELEVANCE = "_relevance_score"
    DISTANCE = "_distance"


def index_exists(index_dir: str | Path) -> bool:
    """True if a LanceDB index (chunks table) exists at *index_dir*."""
    path = Path(index_dir)
    return (path / f"{TABLE_NAME}.lance").is_dir()


def _extract_score(row: dict[str, Any], mode: _ScoreField) -> float:
    """Extract a higher-is-better score from a LanceDB result row.

    Raises:
        ScoreExtractionError: If the expected field is missing.
    """
    field = mode.value
    if field not in row:
        raise ScoreExtractionError(
            f"Expected score field '{field}' not found in LanceDB row. "
            f"Available keys: {sorted(row.keys())}. "
            f"This likely indicates a LanceDB version incompatibility."
        )
    raw = float(row.pop(field))

    for key in ("_relevance_score", "_distance", "distance", "score"):
        row.pop(key, None)

    if mode == _ScoreField.DISTANCE:
        return 1.0 - raw
    return raw


class Store:
    """LanceDB-backed vector store for code chunks."""

    def __init__(self) -> None:
        """Initialize the store from the application config."""
        cfg = get_config()
        self._config = cfg
        self.db_path = Path(cfg.index.path)
        self.dimensions = cfg.embedder.dimensions
        self.metric = cfg.semantic_search.metric
        self._ensure_dir()
        self._db = lancedb.connect(str(self.db_path))
        self._table_known = False
        self._cached_table = None
        self._fts_stale = True
        self._hybrid_failures = 0

    def _ensure_dir(self) -> None:
        """Create the database directory if it does not exist."""
        self.db_path.mkdir(parents=True, exist_ok=True)

    def _table_exists(self) -> bool:
        """Return True when the chunks table is present."""
        if self._table_known:
            return True
        resp = self._db.list_tables()
        tables = resp.tables if hasattr(resp, "tables") else list(resp)
        exists = TABLE_NAME in tables
        if exists:
            self._table_known = True
        return exists

    def _rows_from_chunks_embeddings(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> list[dict[str, Any]]:
        """Convert chunks + embeddings to row dicts for LanceDB.

        Raises:
            EmbeddingDimensionError: On vector/store dimension mismatch.
        """
        rows = []
        for chunk, emb in zip(chunks, embeddings, strict=False):
            if len(emb) != self.dimensions:
                raise EmbeddingDimensionError(
                    f"Embedding dimension {len(emb)} "
                    f"!= store dimension {self.dimensions}"
                )
            rows.append(
                {
                    "path": chunk.path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "symbol": chunk.symbol,
                    "content": chunk.content,
                    "vector": emb,
                }
            )
        return rows

    def _get_table(self):
        """Return the chunks table, caching the reference after first open."""
        if self._cached_table is None:
            self._cached_table = self._db.open_table(TABLE_NAME)
        return self._cached_table

    def _ensure_fts_index(self, table) -> None:
        """Create or replace the Tantivy FTS index on the content column."""
        try:
            table.create_fts_index(
                "content",
                replace=True,
                use_tantivy=True,
            )
        except Exception as exc:
            logger.warning(
                "FTS index creation failed; hybrid search may degrade to "
                "vector-only: %s",
                exc,
            )

    def insert_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """Insert chunks and their embeddings.

        Raises:
            EmbeddingDimensionError: On dimension mismatch.
            ValueError: When chunks and embeddings lengths differ.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        if not chunks:
            return
        rows = self._rows_from_chunks_embeddings(chunks, embeddings)
        if not self._table_exists():
            self._db.create_table(TABLE_NAME, rows)
            self._table_known = True
            self._cached_table = None
        else:
            self._get_table().add(rows)
        self._fts_stale = True

    def delete_by_paths(self, paths: list[str]) -> None:
        """Remove all chunks whose path is in the given list."""
        if not paths:
            return
        if not self._table_exists():
            return
        table = self._get_table()
        safe = [p.replace("'", "''") for p in paths]
        quoted = ", ".join(f"'{p}'" for p in safe)
        table.delete(f"path IN ({quoted})")

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        path_prefix: str | None = None,
        query_text: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run nearest-neighbor search with optional hybrid (vector + BM25) scoring."""
        if not self._table_exists():
            return []
        table = self._get_table()

        use_hybrid = bool(query_text)
        rows = None

        if use_hybrid:
            rows = self._try_hybrid_search(
                table, query_embedding, query_text, top_k, path_prefix
            )
            if rows is None:
                use_hybrid = False

        if rows is None:
            rows = self._vector_search(
                table, query_embedding, top_k, path_prefix
            )

        if use_hybrid:
            self._hybrid_failures = 0

        score_mode = (
            _ScoreField.RELEVANCE if use_hybrid else _ScoreField.DISTANCE
        )
        search_mode = "hybrid" if use_hybrid else "vector"

        results = []
        for r in rows:
            row = dict(r)
            row["score"] = round(float(_extract_score(row, score_mode)), 4)
            row["search_mode"] = search_mode
            row.pop("vector", None)
            results.append(row)

        return results

    def _try_hybrid_search(
        self,
        table,
        query_embedding: list[float],
        query_text: str,
        top_k: int,
        path_prefix: str | None,
    ) -> list[dict] | None:
        """Attempt hybrid search; return None on failure to trigger fallback."""
        if self._fts_stale:
            self._ensure_fts_index(table)
            self._fts_stale = False
        try:
            query = (
                table.search(query_type="hybrid")
                .vector(query_embedding)
                .text(query_text)
                .rerank(reranker=_RERANKER)
            )
            if path_prefix:
                prefix = (path_prefix.rstrip("/") + "/").replace("'", "''")
                query = query.where(f"path LIKE '{prefix}%'")
            return query.limit(top_k).to_list()
        except Exception:
            self._hybrid_failures += 1
            if self._hybrid_failures >= _HYBRID_FAILURE_WARN_THRESHOLD:
                logger.error(
                    "Hybrid search has failed %d consecutive times. "
                    "FTS index is likely corrupted — rebuild with "
                    "'coderay build --full'.",
                    self._hybrid_failures,
                )
            else:
                logger.warning(
                    "Hybrid search failed, falling back to vector-only. "
                    "FTS index may be corrupted — rebuild with "
                    "'coderay build'.",
                    exc_info=True,
                )
            return None

    def _vector_search(
        self,
        table,
        query_embedding: list[float],
        top_k: int,
        path_prefix: str | None,
    ) -> list[dict]:
        """Execute vector-only search."""
        query = table.search(query_embedding).distance_type(self.metric)
        if path_prefix:
            prefix = (path_prefix.rstrip("/") + "/").replace("'", "''")
            query = query.where(f"path LIKE '{prefix}%'")
        return query.limit(top_k).to_list()

    def chunk_count(self) -> int:
        """Total number of chunks in the store."""
        if not self._table_exists():
            return 0
        return self._get_table().count_rows()

    def list_chunks(
        self,
        limit: int = 500,
        path_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        """List indexed chunks (no vectors)."""
        if not self._table_exists():
            return []
        table = self._get_table()
        if table.count_rows() == 0:
            return []

        col_names = ["path", "start_line", "end_line", "symbol"]

        if path_prefix:
            prefix = (path_prefix.rstrip("/") + "/").replace("'", "''")
            arrow = (
                table.search()
                .where(f"path LIKE '{prefix}%'")
                .select(col_names)
                .limit(limit)
                .to_arrow()
            )
        else:
            to_read = min(table.count_rows(), limit)
            arrow = table.head(to_read).select(col_names)

        return arrow.to_pylist()[:limit]

    def chunks_by_path(self) -> dict[str, int]:
        """Return mapping of file path to chunk count."""
        if not self._table_exists():
            return {}
        table = self._get_table()
        n = table.count_rows()
        if n == 0:
            return {}
        arrow = table.head(n).select(["path"])
        paths = arrow.column("path").to_pylist()
        counts: dict[str, int] = {}
        for p in paths:
            key = str(p) if p is not None else "?"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def maintain(self) -> dict[str, Any]:
        """Run maintenance on the chunks table to reclaim space."""
        result: dict[str, Any] = {"cleanup_done": False, "compact_done": False}
        if not self._table_exists():
            return result
        table = self._get_table()
        try:
            dataset = table.to_lance()
        except Exception as e:
            logger.warning("to_lance failed (install pylance?): %s", e)
            result["error_cleanup"] = str(e)
            return result
        try:
            dataset.cleanup_old_versions(retain_versions=1)
            result["cleanup_done"] = True
            logger.info("Cleaned up old table versions")
        except Exception as e:
            logger.warning("cleanup_old_versions failed: %s", e)
            result["error_cleanup"] = str(e)
        try:
            dataset.optimize.compact_files()
            result["compact_done"] = True
            logger.info("Compacted table fragments")
        except Exception as e:
            logger.warning("compact_files failed: %s", e)
            result["error_compact"] = str(e)
        return result

    def clear(self) -> None:
        """Drop table so next insert_chunks creates a fresh one (full rebuild)."""
        if self._table_exists():
            self._db.drop_table(TABLE_NAME)
            self._table_known = False
            self._cached_table = None
            self._fts_stale = True
