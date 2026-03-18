"""Python-specific chunker."""

from __future__ import annotations

import logging

from coderay.core.models import Chunk
from coderay.parsing.base import BaseTreeSitterParser

logger = logging.getLogger(__name__)

MODULE_SYMBOL = "<module>"

# Python tree-sitter node types for chunking
_CHUNK_TYPES = (
    "function_definition",
    "class_definition",
    "decorated_definition",
)


class PythonChunker:
    """Chunk Python files into semantic units."""

    def chunk(self, ctx) -> list[Chunk]:
        """Collect chunks for a Python file."""
        parser = _PythonChunkingParser(ctx)
        try:
            return parser.collect_chunks()
        except Exception as e:  # pragma: no cover
            logger.warning("Chunking failed for %s: %s", ctx.file_path, e)
            return []


class _PythonChunkingParser(BaseTreeSitterParser):
    """Tree-sitter chunker for Python."""

    def collect_chunks(self) -> list[Chunk]:
        """Collect chunks for file."""
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
            if node.type in _CHUNK_TYPES:
                parent = node.parent
                if parent is not None and parent.type in _CHUNK_TYPES:
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
            if child.type in _CHUNK_TYPES:
                continue
            text = self.node_text(child).strip()
            if text:
                lines.append(text)
        return lines
