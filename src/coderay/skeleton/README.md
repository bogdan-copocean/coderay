# skeleton

Extracts a compact API surface from source files: class/function signatures
with docstrings, top-level assignments — no function bodies. Generated on
demand (not stored in the index). Works without a built index.

## How it works

`extractor.py` uses tree-sitter to parse the file, then walks the CST; declaration
nodes come from `LanguageConfig.skeleton.symbol_types` (per language, like chunk
types in `parsing/languages.py`), with shape from `cst` function/class/decorator sets.
Function and method bodies are replaced with `...`. Class headers are kept as
context even when filtering to a specific symbol.

## Symbol filtering

Pass `--symbol ClassName` or `--symbol ClassName.method` to restrict output
to one class or method. Intermediate class headers are preserved for context.

## Why it matters

A skeleton is significantly smaller than the full source — useful for
understanding a file's API before deciding whether to read it in full, and
for feeding to an AI assistant when only the structure matters.
