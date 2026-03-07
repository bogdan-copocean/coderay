# chunking

Breaks source files into semantic units (functions, classes, file preambles)
using tree-sitter syntax tree parsing. These chunks are the units that get
embedded and stored in the vector database.

## How it works

1. `registry.py` defines per-language configs: file extensions, grammar loaders,
   and which syntax tree node types to extract as chunks.
2. `chunker.py` parses a file with tree-sitter, walks the CST, and extracts
   each matching node as a `Chunk`. Top-level code outside definitions
   (imports, constants) is collected into a single `<module>` preamble chunk.

Supported languages: Python, JavaScript, TypeScript, Go.
