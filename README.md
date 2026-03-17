# CodeRay

A local, offline-first semantic code indexer. Builds a vector index,
call/import graph, and file skeletons — exposed as an MCP server for
AI coding assistants and a standalone CLI.

## What you get

| Capability | What it does | Why it matters | AI assistant benefit |
|---|---|---|---|
| **Semantic search** | Find code by meaning, not keywords. "where do we handle auth errors" returns results even if the code never uses that phrase. | Grep finds text. This finds *intent*. | Better context retrieval for plan and edit modes |
| **Blast radius** (`get_impact_radius`) | Given a function or module, show every node reachable within N hops via calls, imports, and inheritance. | Before changing `UserService.save()`, see exactly what breaks. | Safer refactors — agent sees downstream impact before editing |
| **File skeleton** (`get_file_skeleton`) | Signatures, docstrings, imports — no function bodies. The API surface of a file at a glance. | Understand a 500-line file in 30 lines without reading the implementation. | Drastically fewer tokens than reading the full file |
| **Index status** | Chunk count, schema version, branch, last commit, store health. | Confirm the index is fresh before relying on results. | Agent self-checks before trusting search results |

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
      "args": []
    }
  }
}
```

Replace `/path/to/your/.venv/bin/coderay-mcp` with the output of `which coderay-mcp`.

## CLI reference

| Command | Description |
|---|---|
| `coderay watch --repo . [--debounce N]` | **Recommended.** Watch for file changes, re-index automatically |
| `coderay build [--full] --repo .` | One-off build (incremental or full rebuild). Index goes stale while you work |
| `coderay update --repo .` | Incremental update (changed files only) |
| `coderay search "query" [--top-k N]` | Semantic search |
| `coderay list [--by-file]` | List indexed chunks |
| `coderay status` | Index state, branch, commit, chunk count |
| `coderay maintain --repo .` | Compact index, reclaim space |
| `coderay skeleton FILE` | Print file skeleton |
| `coderay graph --kind calls\|imports` | List graph edges |

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
  branch_switch_threshold: 50
  exclude_patterns:  # besides .gitignore
    - "*.log"
```
