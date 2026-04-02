# chunking

Breaks source files into semantic units (functions, classes, file preambles)
using tree-sitter syntax tree parsing. These chunks are the units that get
embedded and stored in the vector database.

## How it works

`chunker.py` parses a file with tree-sitter, walks the CST, and extracts
each matching node as a `Chunk`. Top-level code outside definitions
(imports, module-level constants) is collected into a single `<module>`
preamble chunk.

Nested chunk types under an already-matched chunk are skipped — the parent
chunk's text already covers them.

## Supported languages

Python, JavaScript (`.js`, `.jsx`, `.mjs`, `.cjs`), TypeScript (`.ts`, `.tsx`).

Per-language chunk node types are defined in `parsing/languages.py`
(`ChunkerConfig.chunk_types`).
