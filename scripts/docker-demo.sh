#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 1: Pull embedding model ==="
curl -sf http://ollama:11434/api/pull -d '{"name":"nomic-embed-text"}' \
  | while read -r line; do
    status=$(echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null || true)
    [ -n "$status" ] && echo "  $status"
done
echo ""

echo "=== Step 2: Copy config ==="
mkdir -p .index
cp /repo/scripts/config.ollama.yaml .index/config.yaml
echo "  Using Ollama embedder (nomic-embed-text, 768d)"
echo ""

echo "=== Step 3: Build full index ==="
index -v build --full --repo /repo
echo ""

echo "=== Step 4: Index status ==="
index status
echo ""

echo "=== Step 5: Semantic search ==="
index search "how does the graph extractor work" --top-k 5
echo ""

echo "=== Step 6: Graph ==="
index graph --limit 20
echo ""

echo "=== Step 7: File skeleton ==="
index skeleton /repo/src/indexer/graph/code_graph.py
echo ""

echo "=== Done! ==="
