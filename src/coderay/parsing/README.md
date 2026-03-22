### parsing

Shared Tree-sitter integration: [`base.py`](base.py) (`ParserContext`, `BaseTreeSitterParser`), [`languages.py`](languages.py) (`cst` / `skeleton` / `chunker` per language), [`cst_kind.py`](cst_kind.py) (`classify_node`, `TraversalKind` — reads `lang_cfg.cst`).

**Traversal contracts (different features, same parse stack):**

- **Graph** (`plugins/*/extractor.py`): `classify_node` + dispatch; **function/class** handlers recurse **inside** `_handle_*` with `scope_stack`; outer `_dfs` **returns** after those so bodies are not walked twice from the parent frame.
- **Skeleton** (`skeleton/extractor.py`): uses `classify_node(ntype, lang_cfg)` for structural vs pass-through; **decorated** / **function** / **class** branches keep skeleton-specific emission and `depth`.
- **Chunker** (`chunking/chunker.py`): DFS on `chunker.chunk_types`; **nested** chunk types under a chunk parent are skipped (parent chunk text already covers them). Not routed through `classify_node` (chunk set can differ from graph ordering).
