from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import lancedb

from coderay.core.models import Chunk

logger = logging.getLogger(__name__)

DEFAULT_DIMENSIONS = 384
TABLE_NAME = "chunks"
DEFAULT_DISTANCE_METRIC = "cosine"


def index_exists(index_dir: str | Path) -> bool:
    """True if a LanceDB index (chunks table) exists at index_dir."""
    path = Path(index_dir)
    return (path / f"{TABLE_NAME}.lance").is_dir()


class Store:
    """LanceDB-backed vector store for code chunks."""

    def __init__(self, db_path: str | Path, dimensions: int = DEFAULT_DIMENSIONS):
        """Initialize the LanceDB store."""
        self.db_path = Path(db_path)
        self.dimensions = dimensions
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
        for chunk, emb in zip(chunks, embeddings):
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
        return self._db.open_table(TABLE_NAME)

    def _ensure_fts_index(self, table) -> None:
        """Create or replace the full-text search index on the content column."""
        try:
            table.create_fts_index("content", replace=True)
        except Exception as exc:
            logger.debug("FTS index creation skipped: %s", exc)

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
        """Nearest-neighbor search with optional hybrid scoring."""
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
                    .distance_type(DEFAULT_DISTANCE_METRIC)
                    .text(query_text)
                )
            except Exception:
                query = table.search(query_embedding).distance_type(
                    DEFAULT_DISTANCE_METRIC
                )
                use_hybrid = False
        else:
            query = table.search(query_embedding).distance_type(DEFAULT_DISTANCE_METRIC)

        if path_prefix:
            prefix = (path_prefix.rstrip("/") + "/").replace("'", "''")
            query = query.where(f"path LIKE '{prefix}%'")

        query = query.limit(top_k)
        rows = query.to_list()

        results = []
        for r in rows:
            row = dict(r)
            if "_relevance_score" in row:
                score = row.pop("_relevance_score")
                row.pop("_distance", None)
            elif "_distance" in row:
                score = 1.0 - row.pop("_distance")
            else:
                score = row.pop("distance", 0.0)
            row["score"] = round(float(score), 4)
            row.pop("vector", None)
            results.append(row)

        return results

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
            self._fts_stale = True
