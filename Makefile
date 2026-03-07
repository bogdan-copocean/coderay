# Local semantic code indexer - convenience targets
# Run from repo root.  Index lives in .index/ (gitignored).
# Requires: pip install -e . (registers the `index` entry point)

INDEX_DIR ?= .index
REPO ?= .

.PHONY: install build build-full update search list status maintain skeleton graph \
        test test-cov lint format clean mcp

# ─── Setup ───────────────────────────────────────────────────────────

install:
	pip install -e ".[dev]"

# ─── Indexing ────────────────────────────────────────────────────────

build:
	index --index-dir $(INDEX_DIR) build --repo $(REPO)

build-full:
	index --index-dir $(INDEX_DIR) build --full --repo $(REPO)

update:
	index --index-dir $(INDEX_DIR) update --repo $(REPO)

maintain:
	index --index-dir $(INDEX_DIR) maintain --repo $(REPO)

# ─── Querying ────────────────────────────────────────────────────────

# Usage: make search QUERY="how does auth work" [TOP_K=5]
search:
	@if [ -z "$(QUERY)" ]; then echo "Usage: make search QUERY=\"your query\""; exit 1; fi
	index --index-dir $(INDEX_DIR) search "$(QUERY)" --top-k $(or $(TOP_K),10)

list:
	index --index-dir $(INDEX_DIR) list --by-file

status:
	index --index-dir $(INDEX_DIR) status

# Usage: make skeleton FILE=src/indexer/pipeline/indexer.py
skeleton:
	@if [ -z "$(FILE)" ]; then echo "Usage: make skeleton FILE=path/to/file.py"; exit 1; fi
	index skeleton $(FILE)

# Usage: make graph [KIND=calls] [LIMIT=50]
graph:
	index --index-dir $(INDEX_DIR) graph --kind $(or $(KIND),calls) --limit $(or $(LIMIT),50)

# ─── MCP server ──────────────────────────────────────────────────────

mcp:
	index-mcp

# ─── Dev ─────────────────────────────────────────────────────────────

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=indexer --cov-report=term-missing

lint:
	ruff check src tests --fix
	ruff format --check src tests
	mypy src/indexer

format:
	ruff format src tests
	ruff check src tests --fix --select I

clean:
	rm -rf $(INDEX_DIR)
	rm -rf .pytest_cache __pycache__ src/indexer/__pycache__ tests/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
