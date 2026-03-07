"""Integration test: build graph from real Python files."""

from coderay.graph.builder import build_graph, load_graph, save_graph

SAMPLE_A = "import os\n\ndef greet():\n    print('hello')\n"
SAMPLE_B = "from pathlib import Path\n\nclass Foo:\n    def bar(self):\n        pass\n"


class TestGraphBuildIntegration:
    def test_multi_file_graph(self):
        files = [("a.py", SAMPLE_A), ("b.py", SAMPLE_B)]
        graph = build_graph(".", files)
        assert graph.node_count >= 4  # 2 modules + function + class
        assert graph.edge_count >= 2

    def test_save_load_roundtrip(self, tmp_index_dir):
        files = [("a.py", SAMPLE_A), ("b.py", SAMPLE_B)]
        graph = build_graph(".", files)
        save_graph(graph, tmp_index_dir)
        loaded = load_graph(tmp_index_dir)
        assert loaded is not None
        assert loaded.node_count == graph.node_count
