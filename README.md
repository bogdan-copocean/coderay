# Semantic Code Indexer

A local, offline-first tool that builds a semantic index of your codebase —
enabling meaning-based search, call/import graph queries, and file skeleton
summaries. Ships with an MCP server so AI coding assistants (Claude Code,
Cursor, etc.) can use it as a tool.

## Why

Grep finds exact text. This finds *meaning*. Ask "where do we handle
authentication errors" and get results even if the code never uses that
exact phrase. The code graph answers structural questions: "what calls this
function", "what breaks if I change it", "what does this module import".

## Architecture

```
                        ┌─────────────┐
                        │ Source Code │
                        └──────┬──────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
         ┌─────────────┐ ┌────────────┐ ┌────────────┐
         │  Chunking   │ │   Graph    │ │  Skeleton  │
         │(tree-sitter)│ │  Extract   │ │  Extract   │
         └──────┬──────┘ └─────┬──────┘ └─────┬──────┘
                │             │               │
                ▼             ▼               │
         ┌────────────┐ ┌────────────┐        │
         │  Embedder  │ │ CodeGraph  │        │
         │   (ONNX/   │ │ (NetworkX) │        │
         │   OpenAI/  │ └─────┬──────┘        │
         │   Ollama)  │       │               │
         └──────┬─────┘       │               │
                │             │               │
                ▼             ▼               ▼
         ┌────────────┐ ┌────────────┐   on-demand
         │  LanceDB   │ │ graph.json │  text output
         │  (vectors) │ │            │
         └──────┬─────┘ └─────┬──────┘
                │             │
                └──────┬──────┘
                       ▼
            ┌────────────────────┐
            │   Retrieval API    │
            │  (search + graph)  │
            └─────────┬──────────┘
                      │
              ┌───────┼───────┐
              ▼       ▼       ▼
           ┌─────┐ ┌─────┐ ┌─────┐
           │ CLI │ │ MCP │ │ Py  │
           │     │ │Serve│ │ API │
           └─────┘ └─────┘ └─────┘
```

Every source file is parsed once with **tree-sitter**, then processed three ways:

| Pipeline | What it produces | Stored as |
|---|---|---|
| **Chunking** | Semantic code chunks (functions, classes, file preambles) | Vector embeddings in LanceDB |
| **Graph** | Nodes + edges (IMPORTS, CALLS, DEFINES, INHERITS) | `graph.json` via NetworkX |
| **Skeleton** | Signatures + docstrings, no bodies | Generated on demand |

### Embedding backends

| Backend | Config | Notes |
|---|---|---|
| **Local** (default) | None — works out of the box | `all-MiniLM-L6-v2` via fastembed (ONNX, 384d, no PyTorch) |
| **OpenAI** | `OPENAI_API_KEY` + config | `text-embedding-3-small`, 1536d |
| **Ollama** | Running Ollama server + config | `nomic-embed-text`, 768d |

### Search modes

- **Vector search** — cosine similarity on chunk embeddings
- **Hybrid search** — BM25 full-text + vector with Reciprocal Rank Fusion
- **Structural boosting** — path-based score adjustments (e.g. downrank tests)

### Index features

- **Git-aware**: file discovery via `git ls-files`, automatic branch switch detection
- **Incremental**: only re-embeds files whose content hash changed
- **Resumable**: checkpoint/resume on interruption
- **File-locked**: prevents concurrent index corruption

## Install

**From GitHub (recommended):**

```bash
pip install "semantic-code-indexer[all] @ git+https://github.com/bogdan-copocean/semantic-code-indexer.git"
```

**From a local clone (for development):**

```bash
git clone https://github.com/bogdan-copocean/semantic-code-indexer.git
cd semantic-code-indexer
pip install -e ".[all]"
```

This registers two CLI commands: `index` (main CLI) and `index-mcp` (MCP server).

## Quick start

```bash
cd /path/to/your/project
index build --repo .

# Search by meaning
index search "how does authentication work"

# Explore the call graph
index graph --kind calls

# File API skeleton (signatures only)
index skeleton src/app/main.py
```

## MCP server (Claude Code / Cursor)

Add to `~/.claude/claude_code_config.json` or Cursor MCP settings:

```json
{
  "mcpServers": {
    "semantic-code-indexer": {
      "command": "/path/to/your/.venv/bin/index-mcp",
      "args": []
    }
  }
}
```

### Available tools

| Tool | Description |
|---|---|
| `semantic_search` | Search code by meaning |
| `get_file_skeleton` | File's API surface — signatures, no bodies |
| `trace_callers` | Who calls this function? |
| `trace_callees` | What does this function call? |
| `get_dependencies` | What does this module import? |
| `get_dependents` | What imports this module? |
| `get_subclasses` | All subclasses of a class |
| `get_impact_radius` | Blast radius — what's affected by a change |
| `index_status` | Index health, chunk count, branch info |

## CLI reference

| Command | Description |
|---|---|
| `index build [--full] --repo .` | Build index (incremental or full rebuild) |
| `index update --repo .` | Incremental update (changed files only) |
| `index search "query" [--top-k N]` | Semantic search |
| `index list [--by-file]` | List indexed chunks |
| `index status` | Index state, branch, commit, chunk count |
| `index maintain --repo .` | Compact index, reclaim space |
| `index skeleton FILE` | Print file skeleton |
| `index graph --kind calls\|imports` | List graph edges |

## Configuration

Optional `config.yaml` in the index directory or project root:

```yaml
embedder:
  provider: local           # local | openai | ollama
  model: all-MiniLM-L6-v2
  dimensions: 384

search:
  boost_rules:
    "tests/": 0.5           # downrank test files
    "src/core/": 1.2        # boost core modules
```

## Development

```bash
pip install -e ".[dev]"
make test           # 217 tests
make lint           # ruff + mypy
make format         # auto-format
```

## Requirements

- Python >= 3.10
- Git
- No API keys needed (local embedder is the default)
