# CodeRay

A local, offline-first semantic code indexer. Builds a vector index,
call/import graph, and file skeletons — exposed as an MCP server for
AI coding assistants and a standalone CLI.

## What you get


| Capability                              | What it does                                                                                                                  | Why it matters                                                             | AI assistant benefit                                          |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **Semantic search**                     | Find code by meaning, not keywords. "where do we handle auth errors" returns results even if the code never uses that phrase. | Grep finds text. This finds *intent*.                                      | Better context retrieval for plan and edit modes              |
| **Blast radius** (`get_impact_radius`)  | Given a function or module, show every node reachable within N hops via calls, imports, and inheritance.                      | Before changing `UserService.save()`, see exactly what breaks.             | Safer refactors — agent sees downstream impact before editing |
| **File skeleton** (`get_file_skeleton`) | Signatures, docstrings, imports — no function bodies. The API surface of a file at a glance.                                  | Understand a 500-line file in 30 lines without reading the implementation. | Drastically fewer tokens than reading the full file           |
| **Index status**                        | Chunk count, schema version, branch, last commit, store health.                                                               | Confirm the index is fresh before relying on results.                      | Agent self-checks before trusting search results              |


## Install

Create a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

Then install:

```bash
pip install coderay
```

With all extras (development tools):

```bash
pip install "coderay[all]"
```

With `embedder.backend: auto` (default), CodeRay uses **MLX** on Apple Silicon (those wheels install automatically with `pip install coderay`) and **fastembed** elsewhere (CPU ONNX). Override with `backend: fastembed` or `backend: mlx`. Run `coderay build --full` after switching backends or models.

For development:

```bash
git clone https://github.com/bogdan-copocean/coderay.git
cd coderay
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
```

## Quick start

```bash
cd /path/to/your/project
coderay watch --repo .   # keeps index fresh while you work (recommended)
coderay search "how does authentication work"
coderay graph --kind calls
coderay skeleton src/app/main.py
```

> **Use `watch`, not `build`.** `coderay build` is a one-off; while you work, the index will get stale. `coderay watch` re-indexes on file changes and is the go-to for active development.

## MCP server (Claude Code / Cursor)

Find the MCP executable path:

```bash
which coderay-mcp
```

Add to `~/.claude/claude_code_config.json` or Cursor MCP settings:

```json
{
  "mcpServers": {
    "coderay": {
      "command": "/path/to/your/.venv/bin/coderay-mcp",
      "args": [],
      "env": {
        "CODERAY_INDEX_DIR": "${workspaceFolder}/.index"
      }
    }
  }
}
```

Replace `/path/to/your/.venv/bin/coderay-mcp` with the output of `which coderay-mcp`.

**Important:** Set `CODERAY_INDEX_DIR` so the MCP server finds the index and graph
in your project. Cursor interpolates `${workspaceFolder}` to the workspace root.
Run `coderay build` (or `coderay watch`) from the project root first.

## CLI reference


| Command                                 | Description                                                     |
| --------------------------------------- | --------------------------------------------------------------- |
| `coderay watch --repo . [--debounce N]` | **Recommended.** Watch for file changes, re-index automatically |
| `coderay build [--full] --repo .`       | Build or incremental update. Use `--full` for full rebuild      |
| `coderay search "query" [--top-k N] [--path-prefix P] [--no-tests]` | Semantic search                                                 |
| `coderay list [--by-file]`              | List indexed chunks                                             |
| `coderay status`                        | Index state, branch, commit, chunk count                        |
| `coderay maintain --repo .`             | Compact index, reclaim space                                    |
| `coderay skeleton FILE [--include-imports] [--symbol NAME]` | Print file skeleton (optionally with imports, or filtered to one class/function) |
| `coderay graph [--kind calls\|imports] [--from X] [--to Y] [--limit N]` | List call/import graph edges |
| `coderay impact NODE_ID [--max-depth N]` | Blast radius: callers/dependents of a symbol                   |


## Embedding

Embedding is **offline-first**: models load from the local cache. With **`backend: auto`** (default), Apple Silicon uses MLX (installed as a core dependency on that platform); otherwise ONNX via fastembed on CPU. On first use, if the model is not cached, it downloads automatically (one-time, requires network).

The default model is **Nomic Embed v1.5** (`nomic-ai/nomic-embed-text-v1.5`, 768d, full ONNX). Chunks are embedded as `path`, `symbol`, then source text so identifiers and paths influence retrieval (for example queries like `lancedb` match file paths and symbols, not only error message bodies). Long bodies are tokenized by the model (up to a large context window); `EMBED_MAX_CHARS` caps raw string length (default 120000) to bound memory.

If you change embedder backend, either backend’s model/dimensions, or MLX `max_length`, run **`coderay build --full`** so the index matches the new vectors.

## Configuration

File discovery and ignoring are based on `.git` and `.gitignore`. The `.git` directory is excluded; files matching `.gitignore` are not indexed. Config `exclude_patterns` add extra exclusions on top of that.

Optional `config.yaml` in the index directory (default: `.index/config.yaml`):

```yaml
embedder:
  backend: auto   # auto | fastembed | mlx
  fastembed:
    model: nomic-ai/nomic-embed-text-v1.5
    dimensions: 768
  mlx:
    model: mlx-community/nomicai-modernbert-embed-base-4bit
    dimensions: 768
    max_length: 2048   # increase (e.g. 8192) only if chunks need longer context (slower)

index:
  exclude_patterns:  # besides .gitignore
    - "*.log"

semantic_search:
  hybrid: true   # vector + FTS on path/symbol/body; set false for vector-only
  boosting:
    penalties:
      - pattern: "(^|/)tests?/"
        factor: 0.5
      - pattern: "(^|/)test_[^/]+\\.py$"
        factor: 0.5
    bonuses:
      - pattern: "(^|/)src/"
        factor: 1.1
  metric: cosine

watcher:
  debounce: 2
  exclude_patterns:  # besides .gitignore
    - "*.log"

graph:
  exclude_modules: []   # module names to exclude from CALLS/IMPORTS edges
  include_modules: []  # force-include (override excludes)
```

