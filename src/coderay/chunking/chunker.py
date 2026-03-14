from __future__ import annotations

import logging
from pathlib import Path

from coderay.chunking.registry import LanguageConfig, get_language_for_file
from coderay.core.models import Chunk
from coderay.parsing.base import BaseTreeSitterParser, ParserContext

logger = logging.getLogger(__name__)

MODULE_SYMBOL = "<module>"


class ChunkingTreeSitterParser(BaseTreeSitterParser):
    """Tree-sitter based chunker for source files."""

    def collect_chunks(self) -> list[Chunk]:
        """Collect all chunks for the configured file and language."""
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
                symbol = self._get_symbol_name(node) or f"<{node.type}>"
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

    def _get_symbol_name(self, node) -> str:
        """Extract symbol name from a definition node."""
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type != "decorator":
                    return self._get_symbol_name(child)
            return ""

        for child in node.children:
            if child.type == "identifier":
                return self.node_text(child)
            if child.type in ("class", "def", "func", "function", "type"):
                for sibling in node.children:
                    if sibling.type == "identifier":
                        return self.node_text(sibling)
        if node.type in ("property_identifier", "field_identifier"):
            return self.node_text(node)
        return ""

    def _collect_preamble_lines(self, root) -> list[str]:
        """Collect top-level lines that are NOT part of any chunk_type definition."""
        lines: list[str] = []
        for child in root.children:
            if child.type in self._ctx.lang_cfg.chunker.chunk_types:
                continue
            text = self.node_text(child).strip()
            if text:
                lines.append(text)
        return lines


def _chunk_file_with_config(
    path: str,
    content: str,
    lang_cfg: LanguageConfig,
) -> list[Chunk]:
    """Chunk a file using the provided language configuration."""
    context = ParserContext(file_path=path, content=content, lang_cfg=lang_cfg)
    parser = ChunkingTreeSitterParser(context)
    try:
        return parser.collect_chunks()
    except Exception as e:  # pragma: no cover - defensive logging
        logger.warning("Chunking failed for %s (%s): %s", path, lang_cfg.name, e)
        return []


def chunk_file(path: str | Path, content: str) -> list[Chunk]:
    """Chunk a source file into semantic units (functions, classes, preamble)."""
    path_str = str(path) if isinstance(path, Path) else path
    if not (lang_cfg := get_language_for_file(path_str)):
        logger.warning("No language config for %s ", path_str)
        return []
    return _chunk_file_with_config(path_str, content, lang_cfg)
