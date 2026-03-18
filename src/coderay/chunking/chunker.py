from __future__ import annotations

import logging
from pathlib import Path

from coderay.core.models import Chunk
from coderay.parsing.base import BaseTreeSitterParser, parse_file

logger = logging.getLogger(__name__)

MODULE_SYMBOL = "<module>"


class ChunkingTreeSitterParser(BaseTreeSitterParser):
    """Tree-sitter chunker."""

    def collect_chunks(self) -> list[Chunk]:
        """Collect chunks for file and language."""
        tree = self.get_tree()
        root = tree.root_node
        chunks: list[Chunk] = []

        if preamble_lines := self._collect_preamble_lines(root):
            chunks.append(
                Chunk(
                    path=self.file_path,
                    start_line=1,
                    end_line=root.end_point[0] + 1,
                    symbol=MODULE_SYMBOL,
                    content="\n".join(preamble_lines),
                )
            )

        def _dfs(node) -> None:
            if node.type in self._ctx.lang_cfg.chunker.chunk_types:
                if (
                    node.parent
                    and node.parent.type in self._ctx.lang_cfg.chunker.chunk_types
                ):
                    for child in node.children:
                        _dfs(child)
                    return
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                text = self.node_text(node)
                symbol = self.identifier_from_node(node) or f"<{node.type}>"
                chunks.append(
                    Chunk(
                        path=self.file_path,
                        start_line=start_line,
                        end_line=end_line,
                        symbol=symbol,
                        content=text,
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
    ctx = parse_file(path, content)
    if ctx is None:
        logger.warning("No language config for %s", path)
        return []
    parser = ChunkingTreeSitterParser(ctx)
    try:
        return parser.collect_chunks()
    except Exception as e:  # pragma: no cover - defensive logging
        logger.warning("Chunking failed for %s: %s", path, e)
        return []
