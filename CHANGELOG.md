# Changelog

## 1.2.2 (2026-04-14)

- **MCP / SearchInput** — fix `'SearchInput' object has no attribute '_config'` on every `semantic_search` call; Pydantic `model_validator` fired before `_config` was set ([`cli/search_input.py`](src/coderay/cli/search_input.py)).
- **Tests** — MCP integration tests covering `semantic_search`, `get_file_skeleton`, `get_impact_radius`, and `index_status` against a real in-memory index.
- **Docs** — refine `SKILLS.md` for accuracy: fix MCP args note, drop CLI examples, remove redundant sections.

## 1.2.1 (2026-04-13)

- **Embeddings** — default CPU and MLX models are MiniLM L6 for faster indexing; use BGE Small in config when you need heavier, often stronger embeddings ([`embedding/README.md`](src/coderay/embedding/README.md)).

## 1.2.0 (2026-04-12)

- **Skeleton** — optional file line range: narrow symbols to those fully inside a span (`FILE:START-END`, CLI `--lines`, MCP `file_line_range`); output reflects the requested range.
- **Docs** — add `SKILLS.md` (portable navigation for agents); README and related documentation improvements.

## 1.1.1 (2026-04-09)

- **Graph** — refactor builder toward composition (refs, `ProjectIndex`, callee strategy hook, fact metadata) ([#3](https://github.com/bogdan-copocean/coderay/pull/3)).
- **Graph** — unit tests and README updates ([#4](https://github.com/bogdan-copocean/coderay/pull/4)).
- **CLI / embeddings** — clearer logging: resolved backend and model, batch embedding progress (fastembed and MLX), pipeline timing on `Pipeline done`, phase timings at DEBUG; suppress Hugging Face tqdm warning when progress bars are disabled ([#5](https://github.com/bogdan-copocean/coderay/pull/5)).

## 1.1.0 (2026-04-02)

**CodeRay** is a local-only indexer and assistant toolkit: no LLM inside the product, no API key, no network for core use.

- **Semantic search** — hybrid retrieval (embeddings + BM25, RRF), tuned via `.coderay.toml`.
- **Code graph** — imports, calls, inheritance; **blast radius** (`impact`) to see callers and dependents before you edit.
- **File skeletons** — signatures and docstrings without bodies, for API shape before full reads.
- **CLI** — `init`, `build`, `watch`, `search`, `skeleton`, `impact`, `graph`, `list`, `status`, `maintain`.
- **MCP server** (`coderay-mcp`) — same capabilities for agents (Cursor, Claude Code, etc.); see `AGENTS.md`.
- **Languages** — Python, JavaScript, TypeScript (Tree-sitter).
- **Workspaces** — multi-root / monorepo, optional subtree `include`, `.coderay.toml` as source of truth.
- **Embeddings** — fastembed (CPU) or MLX on Apple Silicon; incremental **watch** re-index.

This release also refreshes onboarding (README, demos) and release metadata.
