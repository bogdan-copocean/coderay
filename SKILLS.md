---
name: coderay-navigation
description: >-
  Before exploring the codebase or loading source content broadly, use CodeRay MCP to
  locate paths and line ranges (search, skeleton, impact), then pull only the snippets you
  need. Same model as README “locate first, then read precisely.” Grep only for exact strings or when
  MCP is wrong.
---

# Must do (two steps)

1. **Locate** — multi calls for: `semantic_search`, `get_file_skeleton`, `get_impact_radius`. Use returned **path + line range** as scope for next step.
2. **Load small** — fetch **only those ranges** (or minimal span). No whole-file pull for **discovery** unless skeleton+ranged slice still insufficient.

## Tool map

| MCP | CLI | Use when |
|-----|-----|----------|
| `semantic_search` | `coderay search` | Intent unknown (“where does X…”) — hits are **candidates** |
| `get_file_skeleton` | `coderay skeleton` | Need API shape — **signatures/docstrings only**, no bodies |
| `get_impact_radius` | `coderay impact` | Before refactor — callers / imports / inheritance |

**Grep:** exact symbol, path, import, error string — not “how does X work.”

**Not grep replacement:** semantic search approximate; verify important edits. Refresh index: `coderay watch` / `coderay build`; check `coderay status` if stale.

# Hard rules

- Never start repo exploration with bulk file dumps when MCP can run — **locate first**.
- After search: **confirm** with skeleton or ranged load on cited lines before big edits.
- Skeleton → pick line numbers → read **those lines**.
- Refactor / behavior change on a symbol → **`get_impact_radius` first**.
- Outside index / binary / generated / you already have exact literal → grep or open target OK; still no "read everything to explore."

# Default order

1. `semantic_search` and/or `get_impact_radius`
2. `get_file_skeleton` for files you edit
3. Load **only** ranges you need

# CLI examples (`coderay skeleton`)

```bash
coderay skeleton path/to/file.py --lines 27-34
coderay skeleton path/to/file.py:27-34
coderay skeleton path/to/file.py --symbol SomeClass
```

## MCP args

Read server `tools/*.json` once per session — **do not** guess parameters.

# More detail

[AGENTS.md](AGENTS.md) · [README.md](README.md)
