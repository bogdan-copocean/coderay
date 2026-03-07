# CodeRay - convenience targets
# Run from repo root.  Index lives in .index/ (gitignored).
# Requires: pip install -e . (registers the `coderay` entry point)

INDEX_DIR ?= .index
REPO ?= .

.PHONY: install build build-full update search list status maintain skeleton graph \
        test test-cov lint format clean mcp

# ─── Setup ───────────────────────────────────────────────────────────

install:
	pip install -e ".[dev]"

# ─── Indexing ────────────────────────────────────────────────────────

build:
	coderay --index-dir $(INDEX_DIR) build --repo $(REPO)

build-full:
	coderay --index-dir $(INDEX_DIR) build --full --repo $(REPO)

update:
	coderay --index-dir $(INDEX_DIR) update --repo $(REPO)

maintain:
	coderay --index-dir $(INDEX_DIR) maintain --repo $(REPO)

# ─── Querying ────────────────────────────────────────────────────────

# Usage: make search QUERY="how does auth work" [TOP_K=5]
search:
	@if [ -z "$(QUERY)" ]; then echo "Usage: make search QUERY=\"your query\""; exit 1; fi
	coderay --index-dir $(INDEX_DIR) search "$(QUERY)" --top-k $(or $(TOP_K),10)

list:
	coderay --index-dir $(INDEX_DIR) list --by-file

status:
	coderay --index-dir $(INDEX_DIR) status

# Usage: make skeleton FILE=src/pipeline/indexer.py
skeleton:
	@if [ -z "$(FILE)" ]; then echo "Usage: make skeleton FILE=path/to/file.py"; exit 1; fi
	coderay skeleton $(FILE)

# Usage: make graph [KIND=calls] [LIMIT=50]
graph:
	coderay --index-dir $(INDEX_DIR) graph --kind $(or $(KIND),calls) --limit $(or $(LIMIT),50)

# ─── MCP server ──────────────────────────────────────────────────────

mcp:
	coderay-mcp

# ─── Dev ─────────────────────────────────────────────────────────────

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	ruff check src tests --fix
	ruff format --check src tests
	mypy src

format:
	ruff format src tests
	ruff check src tests --fix --select I

clean:
	rm -rf $(INDEX_DIR)
	rm -rf .pytest_cache __pycache__ tests/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
