# graph

Directed **calls**, **imports**, and **inheritance** over indexed source. The implementation is laid out as extractors, lowering, merge, and post-merge passes in this package; this file describes **behavior**, not file names.

## Pipeline (conceptual)

Per file: CST → **facts** (definitions, calls, imports, inherits) → **materialise** into `GraphNode` / `GraphEdge`. Multi-file **merge** builds one `CodeGraph`. **Post-merge** runs language passes and global rewrites (e.g. resolving bare-name call targets when unambiguous repo-wide).

Cross-file lowering uses a **module index** (dotted name → file path) so imports and qualified names can become `file_path::symbol` targets. Edges may point at **phantom** strings (unresolved callee) until passes or later tooling refine them.

## Targets and phantoms

Call/import/inherit **targets are strings**: resolved node ids (`file::qual`), module-style refs (`pkg.mod.sym`), or **phantoms** (short names, unknowns). Heuristics classify targets for filtering and UX; **materialise** can emit edges whose endpoints are not yet graph nodes.

**`include_external`** (config) drops edges whose targets are not considered “in repo” for the current index.

## Symbol resolution (`CodeGraph`)

Indexes back **short names** and **qualified names** to node ids. **Unique** short name → one id; **ambiguous** → `resolve_symbol` returns `None` (callers must use full id or disambiguate).

## Impact radius (`impact.py`)

**Reverse** traversal from a symbol: who **calls**, **imports**, or **inherits** toward it, up to a **depth** limit. Not every edge kind is impact-relevant; module nodes are filtered when the same file is already represented by concrete symbols.

**Resolution layers:** exact id → optional **fuzzy** match by trailing name within a file → hints when ambiguous or empty results. **Seeds** for a method can include the **parent class’s** same-named method when inheritance is present, so callers of the base implementation count toward impact on overrides. **Phantom aliases** (same symbol under different string ids) are considered so edges from re-exports or legacy shapes are not missed.

**Limitations:** static graph only—dynamic dispatch, reflection, and cross-repo callers are not modeled; hints may suggest grep when imports exist but call edges could not be resolved.

## Callee lowering (`CalleeResolver`)

Raw callee text from the tree (e.g. `self.m`, `super().x`, `a.b`) is combined with **per-file bindings** (imports, instance typing, scopes) to produce target strings. Order matters: **super** / **self** handling runs before generic **simple** and **dotted-chain** resolution. Behavior is shared across languages where configs align (`self`/`super` prefixes); edge cases differ by language grammar and binding richness.

## Known limitations (general)

- **Soundness:** graph is **heuristic**, not a type system; wrong or missing edges are expected under metaprogramming, conditional imports, and incomplete index scope.
- **Staleness:** graph reflects last build; **watch** / rebuild needed after large refactors.
- **Language coverage:** depth varies by language (Python/JS/TS today); new languages plug in via the same fact/materialise/merge shape but need their own extractors and tests.

## Tests

[`tests/unit/graph/`](../../../tests/unit/graph/) (invariants, extractors, resolver), [`tests/regression/graph/`](../../../tests/regression/graph/) (multi-file fixtures).

## Persistence

`graph.json` under the index directory; **`schema_version`** supports loading older serialised shapes when bumped.
