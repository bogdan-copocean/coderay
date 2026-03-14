### parsing

Shared Tree-sitter integration layer used by `chunking`, `skeleton`, and `graph`.

- **`base.py`**: defines `ParserContext` and `BaseTreeSitterParser`, which own
  file-level parsing state (`file_path`, `content`, `lang_cfg`) and provide
  helpers like `get_tree()`, `node_text()`, `identifier_from_node()`, and
  a generic `walk()` DFS traversal.
- **`languages.py`**: central source of truth for `LanguageConfig` and
  language registries (`get_language_for_file`, `get_supported_extensions`,
  etc.). Node-type tuples (e.g. `chunk_types`, `import_types`) are declarative
  selectors for the syntax nodes that feature modules care about.

Feature modules (`chunking/chunker.py`, `skeleton/extractor.py`,
`graph/extractor.py`) subclass `BaseTreeSitterParser` to implement their own
domain logic while sharing parsing, traversal, and language configuration.

