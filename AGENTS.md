# CodeRay — agent guidance

CodeRay builds a **local index** so agents can **locate** code with paths and line ranges, then **read only what matters** — not whole files by default.

**Runs locally. No LLM in the index. No API key for indexing.**

## Problem and fix

Agents often read entire files because they lack finer location. That burns tokens and floods context. CodeRay answers **where** and **what shape** first: every tool returns **file paths with line ranges** so you narrow, then read a slice.

## Two-phase flow

1. **Locate** — `semantic_search`, `get_file_skeleton`, or `get_impact_radius` (CLI: `coderay search`, `coderay skeleton`, `coderay impact`). Results include path + symbol-level range.
2. **Read precisely** — load only the line range (or minimal span) you need. Full-file reads only when skeleton + range is not enough.

CodeRay augments **grep**, not replaces it: use grep for **exact** strings or symbols; use semantic search for intent when the target name is unknown.

## Token discipline

Full-file reads are expensive; skeleton and targeted search are cheaper. Illustrative numbers and the demo table live in [README.md](README.md). Prefer skeleton or search hits, then ranged reads.

## MCP tools

| Tool | When to use |
|------|-------------|
| `semantic_search` | "How/where" questions — intent-based lookup across the index |
| `get_file_skeleton` | Before reading a file — signatures and docstrings; symbol range + optional file line range |
| `get_impact_radius` | Before refactoring — callers, imports, inheritors |
| `coderay://index/status` | Check freshness before trusting search/impact |

Search results are **candidates** — confirm with `get_file_skeleton` or a ranged read before large edits.

**MCP setup** — server runs against a tree whose root contains `.coderay.toml`; see [README.md](README.md) and [`src/coderay/mcp_server/README.md`](src/coderay/mcp_server/README.md). Env: `CODERAY_REPO_ROOT` = that root.

## CLI (human or scripted)

| Command | Role |
|---------|------|
| `coderay search "query"` | Same intent as `semantic_search` |
| `coderay skeleton FILE` | Same as `get_file_skeleton`; `--lines` / `FILE:START-END`; `--symbol` |
| `coderay impact SYMBOL` | Same as `get_impact_radius` |
| `coderay status` | Index metadata and freshness |
| `coderay build` / `coderay watch` | Rebuild or incremental index |

## Grep vs semantic search

- **Exact symbol or string** → grep/ripgrep.
- **Intent** ("where is retry logic", "how is config loaded") → `semantic_search`.
- **File API surface** → `get_file_skeleton` before a full read.
- **Blast radius** → `get_impact_radius` before changing a symbol.
- **"Which files import this module?"** → grep is fine. **"What calls this across subclasses?"** → `get_impact_radius`.

## When the index might be stale

- Results do not match the tree, impact shows no callers where there should be, or status shows an old commit / `INCOMPLETE`.

Ask the user to run `coderay build` or ensure `coderay watch` is running.

## Node ID format for `get_impact_radius`

```
src/models.py::User.save     # class method
src/utils.py::parse_config   # top-level function
parse_config                 # bare name if unambiguous
```

Ambiguous bare names return candidates to disambiguate.

## Multi-repo workspaces

Each repo has an alias in `.coderay.toml`. Scope `semantic_search` with `repos: ["alias"]` or `repos: ["*"]`; default is `search.default_scope`.

## Monorepo / subtree indexing

Each `[[index.roots]]` entry may set `include` to limit indexed paths.

## Automatic deindexing

`.coderay.toml` defines the index. Removed paths, `include` changes, or new `exclude_patterns` drop stale files on the next build or watch cycle.

## Source of truth

Indexing, excludes, search tuning, and embedder settings live in `.coderay.toml`. If behavior looks wrong, check config, then `coderay status`.

## Portable navigation skill

Full procedure (single file for all agents): [SKILLS.md](SKILLS.md).
