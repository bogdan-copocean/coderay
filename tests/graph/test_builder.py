"""Tests for indexer.graph.builder."""

from coderay.graph.builder import (
    build_and_save_graph,
    build_graph,
    load_graph,
    save_graph,
)

SAMPLE = "import os\n\ndef foo():\n    os.path.exists('.')\n"


class TestBuildGraph:
    def test_builds_from_files(self):
        graph = build_graph(".", [("test.py", SAMPLE)])
        assert graph.node_count > 0
        assert graph.edge_count > 0

    def test_handles_bad_file(self):
        graph = build_graph(".", [("test.py", SAMPLE), ("bad.py", "\x00\x01")])
        assert graph.node_count >= 1


class TestSaveAndLoadGraph:
    def test_roundtrip(self, tmp_index_dir):
        graph = build_graph(".", [("test.py", SAMPLE)])
        save_graph(graph, tmp_index_dir)
        loaded = load_graph(tmp_index_dir)
        assert loaded is not None
        assert loaded.node_count == graph.node_count
        assert loaded.edge_count == graph.edge_count

    def test_load_missing(self, tmp_path):
        assert load_graph(tmp_path) is None

    def test_load_corrupt(self, tmp_index_dir):
        (tmp_index_dir / "graph.json").write_text("not json{{{")
        assert load_graph(tmp_index_dir) is None


class TestBuildAndSaveGraph:
    def test_with_explicit_paths(self, tmp_path, app_config):
        tmp_index_dir = app_config.index.path
        (tmp_path / "a.py").write_text(SAMPLE)
        build_and_save_graph(tmp_path, changed_paths=["a.py"])
        loaded = load_graph(tmp_index_dir)
        assert loaded is not None
        assert loaded.node_count > 0

    def test_incremental_merges_with_existing(self, tmp_path, app_config):
        tmp_index_dir = app_config.index.path
        (tmp_path / "a.py").write_text(SAMPLE)
        (tmp_path / "b.py").write_text("def bar():\n    pass\n")

        build_and_save_graph(tmp_path, changed_paths=["a.py", "b.py"])

        (tmp_path / "b.py").write_text("def bar_v2():\n    pass\n")
        build_and_save_graph(tmp_path, changed_paths=["b.py"])
        updated = load_graph(tmp_index_dir)

        assert updated.node_count > 0
        names = {n["name"] for n in updated.to_dict()["nodes"]}
        assert "foo" in names
        assert "bar_v2" in names
        assert "bar" not in names
