from __future__ import annotations

import logging
from pathlib import Path

from coderay.core.models import Chunk
from coderay.parsing.base import BaseTreeSitterParser, get_parse_context

logger = logging.getLogger(__name__)

MODULE_SYMBOL = "<module>"


class ChunkingTreeSitterParser(BaseTreeSitterParser):
    """Chunk a source file into semantic units using tree-sitter.

    Reads ``lang_cfg.chunker.chunk_types`` to decide which AST nodes
    become chunks. Works for all supported languages.
    """

    def collect_chunks(self) -> list[Chunk]:
        """Collect chunks for file and language."""
        tree = self.get_tree()
        root = tree.root_node
        chunk_types = self._ctx.lang_cfg.chunker.chunk_types
        chunks: list[Chunk] = []

        if preamble_lines := self._collect_preamble_lines(root=root):
            chunks.append(
                Chunk(
                    path=self.file_path,
                    start_line=1,
                    end_line=root.end_point[0] + 1,
                    symbol=MODULE_SYMBOL,
                    content="\n".join(preamble_lines),
                )
            )

        # DFS: top-level chunk nodes become chunks; nested ones are skipped
        # (their parent chunk already contains them).
        def _dfs(node) -> None:
            if node.type in chunk_types:
                parent = node.parent
                if parent is not None and parent.type in chunk_types:
                    for child in node.children:
                        _dfs(child)
                    return
                chunks.append(
                    Chunk(
                        path=self.file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        symbol=(self.identifier_from_node(node) or f"<{node.type}>"),
                        content=self.node_text(node),
                    )
                )
            for child in node.children:
                _dfs(child)

        _dfs(root)
        logger.debug("Chunked %s: %d chunks", self.file_path, len(chunks))
        return chunks

    def _collect_preamble_lines(self, root) -> list[str]:
        """Collect top-level lines outside chunk definitions."""
        lines: list[str] = []
        for child in root.children:
            if child.type in self._ctx.lang_cfg.chunker.chunk_types:
                continue
            text = self.node_text(child).strip()
            if text:
                lines.append(text)
        return lines


def chunk_file(path: str | Path, content: str) -> list[Chunk]:
    """Chunk file into semantic units (functions, classes, preamble)."""
    ctx = get_parse_context(path, content)
    if ctx is None:
        logger.warning("No language config for %s", path)
        return []
    parser = ChunkingTreeSitterParser(ctx)
    try:
        return parser.collect_chunks()
    except Exception as e:  # pragma: no cover - defensive logging
        logger.warning("Chunking failed for %s: %s", path, e)
        return []
