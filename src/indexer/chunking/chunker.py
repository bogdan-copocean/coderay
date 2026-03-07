"""
Tree-sitter based chunker for source code.
Emits (path, range, symbol name, language, text) for functions and classes,
plus a single file-preamble chunk with module-level code (imports, constants,
docstrings) that isn't part of any definition.
"""

from __future__ import annotations

import logging
from pathlib import Path

from indexer.chunking.registry import LanguageConfig, get_language_for_file
from indexer.core.models import Chunk

logger = logging.getLogger(__name__)


def _get_symbol_name(node, source_bytes: bytes) -> str:
    """Extract symbol name from a definition node."""
    for child in node.children:
        if child.type == "identifier":
            return source_bytes[child.start_byte : child.end_byte].decode(
                "utf-8", errors="replace"
            )
        if child.type in ("class", "def", "func", "function", "type"):
            for sibling in node.children:
                if sibling.type == "identifier":
                    return source_bytes[sibling.start_byte : sibling.end_byte].decode(
                        "utf-8", errors="replace"
                    )
    if node.type in ("property_identifier", "field_identifier"):
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )
    return ""


def _collect_preamble_lines(
    root, source_bytes: bytes, chunk_types: tuple[str, ...]
) -> list[str]:
    """Collect top-level lines that are NOT part of any chunk_type definition."""
    lines: list[str] = []
    for child in root.children:
        if child.type in chunk_types:
            continue
        text = (
            source_bytes[child.start_byte : child.end_byte]
            .decode("utf-8", errors="replace")
            .strip()
        )
        if text:
            lines.append(text)
    return lines


def _chunk_file_with_config(
    path: str,
    content: str,
    lang_cfg: LanguageConfig,
) -> list[Chunk]:
    """Chunk a file using the provided language configuration."""
    try:
        parser = lang_cfg.get_parser()
    except Exception as e:
        logger.warning("Could not load parser for %s (%s): %s", path, lang_cfg.name, e)
        return []

    source_bytes = content.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    chunks: list[Chunk] = []

    def visit(node) -> None:
        if node.type in lang_cfg.chunk_types:
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            text = source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
            symbol = _get_symbol_name(node, source_bytes) or f"<{node.type}>"
            chunks.append(
                Chunk(
                    path=path,
                    start_line=start_line,
                    end_line=end_line,
                    symbol=symbol,
                    language=lang_cfg.name,
                    content=text,
                )
            )
        for child in node.children:
            visit(child)

    visit(root)

    preamble_lines = _collect_preamble_lines(root, source_bytes, lang_cfg.chunk_types)
    if preamble_lines:
        preamble_text = "\n".join(preamble_lines)
        chunks.insert(
            0,
            Chunk(
                path=path,
                start_line=1,
                end_line=root.end_point[0] + 1,
                symbol="<module>",
                language=lang_cfg.name,
                content=preamble_text,
            ),
        )

    logger.debug("Chunked %s: %d chunks", path, len(chunks))
    return chunks


def chunk_file(
    path: str | Path,
    content: str,
    language: str = "python",
) -> list[Chunk]:
    """
    Chunk a single file into semantic units (functions, classes).

    Detects the language from file extension if possible, falling back
    to the explicit ``language`` parameter.
    """
    path_str = str(path) if isinstance(path, Path) else path
    lang_cfg = get_language_for_file(path_str)
    if lang_cfg is None:
        from indexer.chunking.registry import LANGUAGE_REGISTRY

        lang_cfg = LANGUAGE_REGISTRY.get(language)
    if lang_cfg is None:
        logger.debug("No language config for %s (language=%s)", path_str, language)
        return []
    return _chunk_file_with_config(path_str, content, lang_cfg)
