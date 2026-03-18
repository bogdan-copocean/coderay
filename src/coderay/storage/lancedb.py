from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import lancedb

from coderay.core.config import get_config
from coderay.core.models import Chunk

logger = logging.getLogger(__name__)

TABLE_NAME = "chunks"


def index_exists(index_dir: str | Path) -> bool:
    """True if a LanceDB index (chunks table) exists at index_dir."""
    path = Path(index_dir)
    return (path / f"{TABLE_NAME}.lance").is_dir()


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
        self._fts_stale = True

    def _ensure_dir(self) -> None:
        self.db_path.mkdir(parents=True, exist_ok=True)

    def _table_exists(self) -> bool:
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
        rows = []
        for chunk, emb in zip(chunks, embeddings, strict=False):
            if len(emb) != self.dimensions:
                raise ValueError(
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
        if not hasattr(self, "_cached_table") or self._cached_table is None:
            self._cached_table = self._db.open_table(TABLE_NAME)
        return self._cached_table

    def _ensure_fts_index(self, table) -> None:
        """Create or replace the full-text search index on the content column."""
        try:
            table.create_fts_index("content", replace=True)
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
        """Insert chunks and their embeddings. Lengths must match."""
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
        """Nearest-neighbor search with optional hybrid scoring.

        Args:
            query_embedding: Dense vector for the query.
            top_k: Maximum results to return.
            path_prefix: Restrict to paths under this directory.
            query_text: When provided, enables hybrid (vector + BM25) search.

        Returns:
            Result dicts with a ``score`` key (higher is better) and a
            ``search_mode`` key (``"hybrid"`` or ``"vector"``).
        """
        if not self._table_exists():
            return []
        table = self._get_table()

        use_hybrid = bool(query_text)
        if use_hybrid:
            if self._fts_stale:
                self._ensure_fts_index(table)
                self._fts_stale = False
            try:
                query = (
                    table.search(query_type="hybrid")
                    .vector(query_embedding)
                    .distance_type(self.metric)
                    .text(query_text)
                )
            except Exception:
                logger.warning(
                    "Hybrid search failed, falling back to vector-only. "
                    "FTS index may be corrupted — rebuild with 'coderay build'.",
                    exc_info=True,
                )
                query = table.search(query_embedding).distance_type(self.metric)
                use_hybrid = False
        else:
            query = table.search(query_embedding).distance_type(self.metric)

        if path_prefix:
            prefix = (path_prefix.rstrip("/") + "/").replace("'", "''")
            query = query.where(f"path LIKE '{prefix}%'")

        query = query.limit(top_k)
        rows = query.to_list()

        search_mode = "hybrid" if use_hybrid else "vector"
        results = []
        for r in rows:
            row = dict(r)
            row["score"] = round(float(self._extract_score(row)), 4)
            row["search_mode"] = search_mode
            row.pop("vector", None)
            results.append(row)

        return results

    @staticmethod
    def _extract_score(row: dict[str, Any]) -> float:
        """Extract a higher-is-better score from a LanceDB result row.

        Handles both hybrid (_relevance_score) and vector (_distance)
        output formats.  Logs a warning if the row contains no
        recognised score field.

        Args:
            row: Mutable dict; recognised score keys are popped.
        """
        if "_relevance_score" in row:
            score = row.pop("_relevance_score")
            row.pop("_distance", None)
            return float(score)

        if "_distance" in row:
            return 1.0 - float(row.pop("_distance"))

        if "distance" in row:
            return float(row.pop("distance"))

        logger.warning(
            "No recognised score field in LanceDB row (keys: %s); "
            "defaulting to 0.0. This may indicate a LanceDB version change.",
            list(row.keys()),
        )
        return 0.0

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
        """List indexed chunks (no vectors). For visualization / debugging."""
        if not self._table_exists():
            return []
        table = self._get_table()
        n = table.count_rows()
        if n == 0:
            return []

        col_names = ["path", "start_line", "end_line", "symbol"]

        if path_prefix:
            prefix = (path_prefix.rstrip("/") + "/").replace("'", "''")
            try:
                arrow = (
                    table.search()
                    .where(f"path LIKE '{prefix}%'")
                    .select(col_names)
                    .limit(limit)
                    .to_arrow()
                )
            except Exception:
                arrow = table.head(min(n, limit * 2))
                arrow = arrow.select(col_names)
                rows = arrow.to_pylist()
                pfix = path_prefix.rstrip("/") + "/"
                return [r for r in rows if str(r.get("path", "")).startswith(pfix)][
                    :limit
                ]
        else:
            to_read = min(n, limit)
            arrow = table.head(to_read)
            arrow = arrow.select(col_names)

        return arrow.to_pylist()[:limit]

    def chunks_by_path(self) -> dict[str, int]:
        """Return mapping of file path -> chunk count for the whole index."""
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
