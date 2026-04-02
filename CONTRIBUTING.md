# Contributing to CodeRay

## Prerequisites

- Python >= 3.10
- Git
- A virtual environment tool (`venv`, `virtualenv`, etc.)

## Setup

```bash
git clone https://github.com/bogdan-copocean/coderay.git
cd coderay
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
```

## Development workflow

```bash
make test          # run all tests
make test-cov      # tests with coverage
make lint          # ruff check + format check + mypy
make format        # auto-format with ruff
```

Run a subset of tests:

```bash
pytest tests/unit -v                    # unit tests only
pytest tests/regression -v              # regression tests only
pytest tests/unit/graph -v              # single module
pytest -k "test_skeleton" -v            # by name pattern
```

## Commit conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(search): add path-prefix filter
fix(graph): handle circular imports
refactor(pipeline): simplify batch logic
test(skeleton): add JS arrow function case
docs(readme): update install instructions
chore(ci): add Python 3.13 to matrix
```

Breaking changes use `!` after the type: `feat(config)!: require TOML v2 format`

## Pull requests

- One concern per PR — keep it focused
- Tests pass (`make test`)
- Lint clean (`make lint`)
- Include a brief description of **what** and **why**
- Link related issues

## Architecture

Each module under `src/coderay/` has its own `README.md` explaining its role. Start with [`src/README.md`](src/README.md) for the full map.

Key modules:

| Module | Role |
|--------|------|
| `parsing/` | Tree-sitter grammars and language configs |
| `chunking/` | Split files into embeddable chunks |
| `embedding/` | Local embedding backends (fastembed, MLX) |
| `retrieval/` | Hybrid vector + BM25 search |
| `graph/` | Call/import/inheritance graph |
| `skeleton/` | Signature extraction (no bodies) |
| `pipeline/` | Indexing orchestration and file watching |
| `mcp_server/` | MCP stdio server for editors |
| `cli/` | Click CLI commands |

## Adding a new language

CodeRay uses tree-sitter for parsing. To add a language:

1. Add the tree-sitter grammar to `pyproject.toml` dependencies
2. Add a `ChunkerConfig` and `LanguageConfig` in `src/coderay/parsing/languages.py`
3. Add skeleton and graph extraction support
4. Add tests in `tests/unit/` and `tests/regression/`

See [`parsing/README.md`](src/coderay/parsing/README.md) for details.

## Good first issues

Look for issues labeled [`good first issue`](https://github.com/bogdan-copocean/coderay/labels/good%20first%20issue). These are scoped, well-defined tasks suitable for new contributors.
