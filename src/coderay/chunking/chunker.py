from __future__ import annotations

import logging
from pathlib import Path

from coderay.chunking.registry import LanguageConfig, get_language_for_file
from coderay.core.models import Chunk

logger = logging.getLogger(__name__)


def _get_symbol_name(node, source_bytes: bytes) -> str:
    """Extract symbol name from a definition node."""
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type != "decorator":
                return _get_symbol_name(child, source_bytes)
        return ""

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

    def dfs(node) -> None:
        if node.type in lang_cfg.chunk_types:
            # [py] Avoid duplicates on decorated functions.
            # [py] Decorators are stored with symbol of the function that is decorating
            # [py] But the content field of the decorated function will capture them
            if node.parent and node.parent.type in lang_cfg.chunk_types:
                for child in node.children:
                    dfs(child)
                return
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
            dfs(child)

    if preamble_lines := _collect_preamble_lines(
        root, source_bytes, lang_cfg.chunk_types
    ):
        chunks.append(
            Chunk(
                path=path,
                start_line=1,
                end_line=root.end_point[0] + 1,
                symbol="<module>",
                language=lang_cfg.name,
                content="\n".join(preamble_lines),
            ),
        )

    dfs(root)

    logger.debug("Chunked %s: %d chunks", path, len(chunks))
    return chunks


def chunk_file(path: str | Path, content: str, language: str = "python") -> list[Chunk]:
    """Chunk a source file into semantic units (functions, classes, preamble)."""
    path_str = str(path) if isinstance(path, Path) else path
    if not (lang_cfg := get_language_for_file(path_str)):
        logger.warning("No language config for %s ", path_str)
        return []
    return _chunk_file_with_config(path_str, content, lang_cfg)
