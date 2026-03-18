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

With all extras (JS/TS/Go support, MCP server tools):

```bash
pip install "coderay[all]"
```

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
| `coderay search "query" [--top-k N]`    | Semantic search                                                 |
| `coderay list [--by-file]`              | List indexed chunks                                             |
| `coderay status`                        | Index state, branch, commit, chunk count                        |
| `coderay maintain --repo .`             | Compact index, reclaim space                                    |
| `coderay skeleton FILE`                 | Print file skeleton                                             |
| `coderay graph --kind calls             | imports`                                                        |


## Embedding

Embedding is **offline-first**: the model loads from the local cache only, with no HuggingFace API calls. On first use, if the model is not cached, it downloads automatically (one-time, requires network). No manual steps.

If you previously used a different model, run `coderay build --full` after upgrading.

## Configuration

File discovery and ignoring are based on `.git` and `.gitignore`. The `.git` directory is excluded; files matching `.gitignore` are not indexed. Config `exclude_patterns` add extra exclusions on top of that.

Optional `config.yaml` in the index directory (default: `.index/config.yaml`):

```yaml
embedder:
  model: sentence-transformers/all-MiniLM-L6-v2
  dimensions: 384

index:
  exclude_patterns:  # besides .gitignore
    - "*.log"

semantic_search:
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

