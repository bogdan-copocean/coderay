# CodeRay — X-ray your codebase

[![PyPI](https://img.shields.io/pypi/v/coderay)](https://pypi.org/project/coderay/)
[![License](https://img.shields.io/github/license/bogdan-copocean/coderay)](LICENSE)
[![CI](https://github.com/bogdan-copocean/coderay/actions/workflows/ci.yml/badge.svg)](https://github.com/bogdan-copocean/coderay/actions/workflows/ci.yml)

**CodeRay** ships a **local code index** with **semantic search**, **file skeletons** (signatures and docstrings, no bodies), and **blast radius** (callers, imports, inheritance) — plus an **MCP stdio server** so agents can use the same tools. Ask *by meaning*, skim **API shape**, trace **who calls what**, then read implementation when it matters: fewer tokens, less noise, answers anchored to the right files.

**No LLM inside CodeRay, no network, no API key – it runs on your machine.**


## Tools

**CodeRay sits next to ripgrep, not instead of it.** Ripgrep when you know the string or symbol; search, skeleton, and impact when you care about *intent*, *structure*, or *dependencies*—then open the file when you need real implementation detail.

Semantic search is retrieval, not proof: hits can miss or rank oddly. Treat them as candidates, confirm with a skeleton or read, and keep the index fresh with `coderay watch` or `coderay build` when things drift.

Skeleton shows API shape and docstrings, not every branch. Use **search** and **impact** to narrow where to look, then read the file (or spans) when you need control flow or line-accurate edits. CodeRay trims noise on those round trips; it does not forbid them.

**Semantic search** — “How/where” by meaning.

<img src="assets/coderay-search.gif" alt="coderay search demo" width="100%" />

### Blast radius

Callers and dependents (calls, imports, inheritance).

<img src="assets/coderay-impact.gif" alt="coderay impact demo" width="100%" />

### Skeleton

Signatures and docstrings only; API surface without bodies.

<img src="assets/coderay-skeleton.gif" alt="coderay skeleton demo" width="100%" />

### Full read

Same file as skeleton: raw source costs more tokens.

<img src="assets/coderay-fullread.gif" alt="same file, raw source head" width="100%" />

### First run

`coderay init` and `coderay build`.

<img src="assets/coderay.gif" alt="coderay init and build" width="100%" />

**Status** — `coderay status`: chunks, branch, commit, schema.


## MCP

Same tools as above, exposed to the agent so it can search, sketch structure, and trace impact instead of vacuuming whole files by default. Point the server at a checkout whose root contains `.coderay.toml` (`CODERAY_REPO_ROOT` below). For choosing tools versus a plain read, see [AGENTS.md](AGENTS.md).

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


## Why this matters

Noisy context windows make models confident about the wrong code. CodeRay front-loads **intent** (search), **shape** (skeleton), and **dependencies** (impact) so the expensive read happens after you have a map—not instead of ever reading implementation when control flow matters.

### Token savings (tiktoken, `cl100k_base`)

Measured on this repo after a full index.


| File                               | Lines | Full read | Skeleton | Savings  |
| ---------------------------------- | ----- | --------- | -------- | -------- |
| `src/coderay/pipeline/indexer.py`  | 400   | 3,024     | 757      | **4.0x** |
| `src/coderay/graph/code_graph.py`  | 500   | 4,261     | 1,022    | **4.2x** |
| `src/coderay/mcp_server/server.py` | 316   | 2,268     | 1,313    | **1.7x** |



| Query                                | Search hit tokens | vs full `indexer.py` read |
| ------------------------------------ | ----------------- | ------------------------- |
| "how are files re-indexed on change" | 479               | **~6x cheaper**           |


*Not guarantees — model, chunks, and files affect counts.*

---

## Features

- **Languages** — Python, JavaScript, and TypeScript — [`parsing/README.md`](src/coderay/parsing/README.md)
- **Multi-repo / monorepo** — roots, aliases, optional `include` subtrees — [`core/README.md`](src/coderay/core/README.md)
- **Hybrid search** — vector + BM25 (RRF), optional boosting — [`retrieval/README.md`](src/coderay/retrieval/README.md)
- **Embeddings** — fastembed (CPU) or MLX on Apple Silicon — [`embedding/README.md`](src/coderay/embedding/README.md)
- **Watch** — incremental re-index; `.coderay.toml` is the source of truth for what’s indexed

---

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