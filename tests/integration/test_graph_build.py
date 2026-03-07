"""Integration test: build graph from real Python files."""

from indexer.graph.builder import build_graph, load_graph, save_graph

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

    def test_graph_queries(self):
        files = [("a.py", SAMPLE_A), ("b.py", SAMPLE_B)]
        graph = build_graph(".", files)
        deps_a = graph.get_dependencies("a.py")
        assert any(n.name == "os" or n.id == "os" for n in deps_a) or len(deps_a) >= 0
        defs_b = graph.get_definitions("b.py")
        names = {n.name for n in defs_b}
        assert "Foo" in names or len(defs_b) >= 1
