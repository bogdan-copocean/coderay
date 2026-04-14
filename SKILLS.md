---
name: coderay-navigation
description: >-
  Before exploring the codebase or loading source content broadly, use CodeRay MCP to
  locate paths and line ranges (search, skeleton, impact), then pull only the snippets you
  need: "locate first, then read precisely." Grep for exact strings or literals; semantic
  search for intent. Fall back to grep when index is stale, unavailable or unhelpful.
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

**MCP args:** schemas provided by protocol — use directly, do not guess.

# Hard rules

- Never start repo exploration with bulk file dumps when MCP can run — **locate first**.
- After search: **confirm** with skeleton or ranged load on cited lines before big edits.
- Skeleton → pick line numbers → read **those lines**.
- Refactor / behavior change on a symbol → **`get_impact_radius` first**.
- Outside index / binary / generated / you already have exact literal → grep or open target OK; still no "read everything to explore."

