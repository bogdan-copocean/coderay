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
pip install -e ".[all]"
```

## Quick start

```bash
cd /path/to/your/project
coderay build --repo .
coderay search "how does authentication work"
coderay watch --repo .
coderay graph --kind calls
coderay skeleton src/app/main.py
```

## MCP server (Claude Code / Cursor)

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

## CLI reference

| Command | Description |
|---|---|
| `coderay build [--full] --repo .` | Build index (incremental or full rebuild) |
| `coderay update --repo .` | Incremental update (changed files only) |
| `coderay watch --repo . [--debounce N]` | Watch for file changes, re-index automatically |
| `coderay search "query" [--top-k N]` | Semantic search |
| `coderay list [--by-file]` | List indexed chunks |
| `coderay status` | Index state, branch, commit, chunk count |
| `coderay maintain --repo .` | Compact index, reclaim space |
| `coderay skeleton FILE` | Print file skeleton |
| `coderay graph --kind calls\|imports` | List graph edges |

## Configuration

Optional `config.yaml` in the index directory:

```yaml
embedder:
  provider: local
  model: all-MiniLM-L6-v2
  dimensions: 384

search:
  boost_rules:
    "tests/": 0.5
    "src/core/": 1.2

graph:
  exclude_callees:
    - "our_sdk_helper"
  include_callees:
    - "isinstance"

watch:
  debounce_seconds: 2
  branch_switch_threshold: 50
  exclude_patterns:
    - "*.log"
```

## Development

```bash
pip install -e ".[dev]"
make test
make lint
make format
```

Requires Python >= 3.10 and Git.
