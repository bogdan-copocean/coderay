# CodeRay — X-ray your codebase

[![PyPI](https://img.shields.io/pypi/v/coderay)](https://pypi.org/project/coderay/)
[![License](https://img.shields.io/github/license/bogdan-copocean/coderay)](LICENSE)
[![CI](https://github.com/bogdan-copocean/coderay/actions/workflows/ci.yml/badge.svg)](https://github.com/bogdan-copocean/coderay/actions/workflows/ci.yml)

**CodeRay** builds a **local code index** that gives AI agents a smarter way to explore a codebase — reading only what they need, not whole files.

**Runs locally. No LLM. No network. No API key.**

## The problem

AI agents exploring a codebase default to reading whole files – even when one function is all that's needed. Every unnecessary line **burns tokens** and **floods the context window**: driving up API costs and noise with every read.

The root cause is simple: agents know the **file paths** but no finer location. Without knowing *where* in a file something lives, they have no choice but to read everything.

**CodeRay fixes this.** Every tool returns **file paths with exact line ranges** — so agents locate first, then read only the lines that matter.

## How it works

CodeRay exposes three primitives, each returning **paths + line ranges**:

| Tool | Question it answers | What agents get |
|------|---------------------|-----------------|
| **search** | *Where is the code that does X?* | Relevant chunks with file paths and line ranges |
| **skeleton** | *What's the shape of this file?* | Signatures + docstrings only, each tagged with its line range |
| **impact** | *What breaks if I change this?* | Callers, imports, and inheritors — located by line range |

### The two-phase flow

1. **Locate** — run `search`, `skeleton`, or `impact` to find what's needed. Every result includes a file path and a symbol-level line range.
2. **Read precisely** — use those line ranges to load only the relevant snippet. Skip the rest.

This keeps context windows lean and agent reasoning focused. CodeRay is not a replacement for `grep` — it fills the gap when exact names are unknown or a map is needed before reading.

### Token savings (tiktoken, `cl100k_base`)

| File | Lines | Full read | Skeleton | Savings | % reduction |
|------|-------|-----------|----------|---------|-------------|
| `src/coderay/graph/impact.py` | 249 | 2,333 | 693 | **3.4×** | **70%** |
| `src/coderay/cli/commands.py` | 584 | 4,327 | 1,906 | **2.3×** | **56%** |
| `src/coderay/pipeline/indexer.py` | 408 | 3,065 | 1,433 | **2.1×** | **53%** |

| Query | Search hit tokens | vs full `indexer.py` read |
|-------|-------------------|---------------------------|
| "how are files re-indexed on change" | 479 | **~6x cheaper** |


## Tools

### Semantic search

Agents search by **meaning**, not by name — useful when the exact function or class is unknown. Results return **file paths with line ranges** pointing at relevant chunks. Treat them as candidates: confirm with `skeleton` or a ranged read before acting. Keep the index fresh with `coderay watch` or `coderay build` when the tree drifts.

<img src="assets/coderay-search.gif" alt="coderay search demo" width="100%" />

### Blast radius

Shows **callers, imports, and inheritance** for a symbol before it changes. Each result is tied to a file path and line range — combine with `skeleton` or ranged reads on those locations when bodies are needed.

<img src="assets/coderay-impact.gif" alt="coderay impact demo" width="100%" />

### Skeleton

Returns **signatures and docstrings only** — no function bodies. Every block is tagged with its path and line range so subsequent reads can be scoped to exactly those lines. A full file read should happen only when the skeleton isn't enough.

<img src="assets/coderay-skeleton.gif" alt="coderay skeleton demo" width="100%" />

### Full read

**Same file, raw source — for comparison:**

<img src="assets/coderay-fullread.gif" alt="same file, raw source head" width="100%" />

### First run

`coderay init` and `coderay build`.

<img src="assets/coderay.gif" alt="coderay init and build" width="100%" />

**Status** — `coderay status`: chunks, branch, commit, schema.


## MCP

Same three tools over MCP: search, skeleton (paths and line ranges), and impact—so **AI agents** can **narrow context** before full-file reads. Point the server at a checkout whose root contains `.coderay.toml` (`CODERAY_REPO_ROOT` below). For tool choice versus a plain read, see [AGENTS.md](AGENTS.md).

```bash
which coderay-mcp
```

```json
{
  "mcpServers": {
    "coderay": {
      "command": "/path/to/.venv/bin/coderay-mcp",
      "args": [],
      "env": { "CODERAY_REPO_ROOT": "${workspaceFolder}" }
    }
  }
}
```

`CODERAY_REPO_ROOT` must be the directory that contains `.coderay.toml`. More detail: [`mcp_server/README.md`](src/coderay/mcp_server/README.md).


## Features

- **Languages** — Python, JavaScript, and TypeScript — [`parsing/README.md`](src/coderay/parsing/README.md)
- **Multi-repo / monorepo** — roots, aliases, optional `include` subtrees — [`core/README.md`](src/coderay/core/README.md)
- **Hybrid search** — vector + BM25 (RRF), optional boosting — [`retrieval/README.md`](src/coderay/retrieval/README.md)
- **Embeddings** — fastembed (CPU) or MLX on Apple Silicon; defaults to MiniLM L6 for speed — configure BGE in `.coderay.toml` for stronger (heavier) vectors — [`embedding/README.md`](src/coderay/embedding/README.md)
- **Watch** — incremental re-index; `.coderay.toml` is the source of truth for what’s indexed


## Install

**pipx (no venv):**

```bash
brew install pipx && pipx install coderay   # macOS
# Linux: python3 -m pip install --user pipx && pipx install coderay
```

**In a project:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install coderay
# Apple Silicon (optional): pip install "coderay[mlx]"
```

**From source:** `pip install -e ".[all]"` — see [CONTRIBUTING.md](CONTRIBUTING.md).


## Quick start

```bash
cd /path/to/your/project
coderay init
coderay watch
coderay search "how does authentication work"
coderay skeleton src/app/main.py
coderay impact some_symbol
```


## CLI

| Command                   | Description                                                |
| ------------------------- | ---------------------------------------------------------- |
| `coderay init`            | Create `.coderay.toml` and `.coderay/`                     |
| `coderay watch [--quiet]` | Re-index on file changes                                   |
| `coderay build [--full]`  | One-off or full rebuild                                    |
| `coderay search "query"`  | Semantic search (`--top-k`, `--path-prefix`, `--no-tests`) |
| `coderay skeleton FILE`   | Signatures (`--symbol`)                                    |
| `coderay impact SYMBOL`   | Blast radius (`--max-depth`)                               |
| `coderay graph`           | List edges (`--from`, `--to`, `--kind`)                    |
| `coderay list`            | Chunks or per-file summary                                 |
| `coderay status`          | Index metadata                                             |
| `coderay maintain`        | Compact LanceDB                                            |


## Configuration

`coderay init` writes an annotated `.coderay.toml`: `[index]`, `[search]`, `[graph]`, `[embedder]`, `[watcher]`. See module READMEs linked from [`src/README.md`](src/README.md).


## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md)


## Accuracy and limitations

Semantic search is approximate (model and chunks matter). **No warranty** — MIT License. Evaluate on your own codebase.