# parsing

Shared tree-sitter integration: grammar loading, CST traversal dispatch,
and per-language configuration.

## Files

- `languages.py` — `LANGUAGE_REGISTRY`: per-language config objects
  (`PythonConfig`, `JavaScriptConfig`, `TypeScriptConfig`) defining
  extensions, grammar loader, CST dispatch rules, skeleton config,
  chunker config, and graph config. `get_language_for_file(path)` resolves
  by extension.
- `base.py` — `ParserContext` (language + grammar handle) and
  `BaseTreeSitterParser` (builds the tree-sitter `Parser` on demand).
- `cst_kind.py` — `classify_node(ntype, lang_cfg)` returns a `TraversalKind`
  (`IMPORT`, `FUNCTION`, `CLASS`, `DECORATOR`, `OTHER`) used by both the
  graph extractor and skeleton extractor.
- `conventions.py` — naming helpers shared across plugins.

## Supported languages

Python (`.py`, `.pyi`), JavaScript (`.js`, `.jsx`, `.mjs`, `.cjs`),
TypeScript (`.ts`, `.tsx`).

## Traversal contracts

Three features share the same parse stack but walk it differently:

- **Graph** (`graph/plugins/*/extractor.py`): `classify_node` + dispatch;
  function/class handlers recurse inside `_handle_*` with a scope stack;
  outer DFS returns after those to avoid double-walking.
- **Skeleton** (`skeleton/extractor.py`): `classify_node` for structural
  dispatch; emits signatures at the right depth without bodies.
- **Chunker** (`chunking/chunker.py`): DFS on `chunker.chunk_types`; skips
  nested matches (parent chunk text already covers them). Not routed through
  `classify_node`.
