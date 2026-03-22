# skeleton

Extracts a compact API surface from source files: imports, class/function
signatures with docstrings, top-level assignments — no function bodies.
Generated on demand (not stored). Uses tree-sitter for parsing.
Structural dispatch aligns with [`parsing/cst_kind.py`](../parsing/cst_kind.py) (`classify_node`).
