"""Tests for graph.builder."""

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


class TestCrossFileResolution:
    """Test cross-file CALLS edges are pre-resolved."""

    def test_build_graph_resolves_cross_file_function_call(self):
        """File A imports and calls a function from file B."""
        file_b = "def compute(x):\n    return x * 2\n"
        file_a = "from lib.math import compute\n\ndef run():\n    compute(42)\n"
        graph = build_graph(
            ".",
            [
                ("src/lib/math.py", file_b),
                ("src/app/main.py", file_a),
            ],
        )

        result = graph.get_impact_radius("src/lib/math.py::compute", depth=2)
        ids = {n.id for n in result.nodes}
        assert "src/app/main.py::run" in ids

    def test_build_graph_resolves_cross_file_class_method_call(self):
        """File A imports a module and calls a class via attribute access."""
        file_b = (
            "class Formatter:\n"
            "    def format_text(self, text):\n"
            "        return text.strip()\n"
        )
        file_a = (
            "from lib import formatter\n\ndef process():\n    formatter.Formatter()\n"
        )
        graph = build_graph(
            ".",
            [
                ("src/lib/formatter.py", file_b),
                ("src/app/worker.py", file_a),
            ],
        )

        edges = graph.to_dict()["edges"]
        calls = [e for e in edges if e["kind"] == "calls"]
        call_targets = {e["target"] for e in calls}
        assert any("Formatter" in t for t in call_targets)

    def test_build_graph_resolves_cross_file_imported_function(self):
        """Direct call to an imported function resolves at extraction time."""
        file_b = "def validate(data):\n    return bool(data)\n"
        file_a = (
            "from core import validator\n\ndef handle():\n    validator.validate({})\n"
        )
        graph = build_graph(
            ".",
            [
                ("src/core/validator.py", file_b),
                ("src/api/handler.py", file_a),
            ],
        )

        result = graph.get_impact_radius("src/core/validator.py::validate", depth=2)
        ids = {n.id for n in result.nodes}
        assert "src/api/handler.py::handle" in ids

    def test_impact_radius_includes_decorator_callers(self):
        """Changing a decorator should show decorated callers in impact radius."""
        decorator = "def my_decorator(fn):\n    return fn\n"
        consumer = (
            "from pkg.decorators import my_decorator\n\n"
            "@my_decorator\n"
            "def foo():\n"
            "    pass\n"
        )
        graph = build_graph(
            ".",
            [
                ("src/pkg/decorators.py", decorator),
                ("src/app/main.py", consumer),
            ],
        )
        result = graph.get_impact_radius("src/pkg/decorators.py::my_decorator", depth=2)
        ids = {n.id for n in result.nodes}
        assert "src/app/main.py" in ids

    def test_rewrites_package_re_export_phantom_targets(self):
        """CALLS edges to package::Symbol.method are rewritten to real node IDs.

        When importing from a package __init__ that re-exports from a submodule,
        the extractor resolves to package::Symbol. The rewrite step resolves by
        qualified name and rewrites the edge before phantom pruning.
        """
        pkg_init = "from .service import UserService\n"
        pkg_service = (
            "class UserService:\n"
            "    def get_user_by_id(self, id: int):\n"
            "        return None\n"
        )
        caller = (
            "from pkg import UserService\n\n"
            "def handle(user_service: UserService):\n"
            "    user_service.get_user_by_id(1)\n"
        )
        graph = build_graph(
            ".",
            [
                ("src/pkg/__init__.py", pkg_init),
                ("src/pkg/service.py", pkg_service),
                ("src/app/caller.py", caller),
            ],
        )

        result = graph.get_impact_radius(
            "src/pkg/service.py::UserService.get_user_by_id", depth=2
        )
        ids = {n.id for n in result.nodes}
        assert "src/app/caller.py::handle" in ids


class TestPhantomPruning:
    """Ambiguous bare-name CALLS to phantoms are pruned."""

    def test_ambiguous_bare_name_calls_pruned(self):
        """CALLS edges to bare-name phantom with multiple candidates are removed."""
        file_a = (
            "class RepoA:\n"
            "    def save(self, data):\n"
            "        pass\n"
        )
        file_b = (
            "class RepoB:\n"
            "    def save(self, data):\n"
            "        pass\n"
        )
        file_c = (
            "def handler(repo):\n"
            "    repo.save({})\n"
        )
        graph = build_graph(
            ".",
            [
                ("src/repo_a.py", file_a),
                ("src/repo_b.py", file_b),
                ("src/handler.py", file_c),
            ],
        )
        edges = graph.to_dict()["edges"]
        phantom_save_edges = [
            e for e in edges
            if e["kind"] == "calls" and e["target"] == "save"
        ]
        assert len(phantom_save_edges) == 0, (
            "ambiguous bare-name 'save' CALLS should be pruned"
        )
