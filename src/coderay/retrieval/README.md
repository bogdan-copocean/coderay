# retrieval

Search orchestration between the CLI/MCP and the vector store.

## Pipeline

```
Retrieval.search()
    ↓ embed query (EmbedTask.QUERY)
    ↓ Store.search() — overfetches top_k*2 to absorb dedup losses
    ↓ StructuralBooster.boost() — path-regex score multipliers
    ↓ _deduplicate_by_containment() — drop enclosing spans
    ↓ trim to top_k
    ↓ _assign_relevance() — tag 'high' / 'medium' / 'low' tiers
```

## Files

- `search.py` — `Retrieval` orchestrates the pipeline above.
- `boosting.py` — `StructuralBooster` applies regex-based path multipliers
  (penalties and bonuses) to re-rank results after retrieval.
- `models.py` — `SearchResult`, `SearchRequestDTO`, `Relevance` type.

## Hybrid search

When `search.hybrid = true` (default), `Store.search` combines dense vector
similarity with BM25 lexical search on a `search_text` field (`path + symbol
+ content`) using RRF reranking. This means keyword-style queries (identifiers,
file names, library names) surface alongside intent-based queries.
Set `hybrid = false` in `.coderay.toml` to use vector-only search.

## Boosting

`[search.boosting]` in `.coderay.toml` accepts `penalties` and `bonuses` —
each a regex pattern and a score multiplier. Defaults down-rank test files
and up-rank `src/`. Rules are cumulative; add your own to tune for your
project layout.

## Relevance tiers

Results are tagged `high`, `medium`, or `low` based on score drop boundaries
(a result whose score is less than 50% of the previous result's score marks a
tier boundary). Tiers are informational — returned in the result dict for the
caller to use as they see fit.
