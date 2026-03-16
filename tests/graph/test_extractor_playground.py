"""Playground tests for graph extraction on tree_sitter_playground.py.

Use this file to experiment with the graph extractor. Add assertions,
print nodes/edges, or tweak the sample code to explore behavior.
"""

from pathlib import Path

import pytest

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.extractor import extract_graph_from_file

PLAYGROUND_PATH = Path(__file__).parent.parent / "tree_sitter_playground.py"


@pytest.fixture
def playground_graph():
    """Extract graph from tree_sitter_playground.py."""
    content = PLAYGROUND_PATH.read_text()
    return extract_graph_from_file(str(PLAYGROUND_PATH), content)


class TestGraphPlayground:
    """Playground: tweak these tests or add new ones to explore the extractor."""

    def test_extracts_all_classes(self, playground_graph):
        """Verify all 5 classes are found."""
        nodes, _ = playground_graph
        classes = [n for n in nodes if n.kind == NodeKind.CLASS]
        names = {n.name for n in classes}
        assert names == {
            "BaseService",
            "FileService",
            "User",
            "Repository",
            "DecoratedClass",
        }

    def test_extracts_nested_functions(self, playground_graph):
        """Verify nested functions (decorator.wrapper, tracing.inner) are found."""
        nodes, _ = playground_graph
        funcs = [n for n in nodes if n.kind == NodeKind.FUNCTION]
        qualified = {n.qualified_name for n in funcs}
        assert "decorator.wrapper" in qualified
        assert "tracing.inner" in qualified

    def test_file_service_inherits_base_service(self, playground_graph):
        """Verify FileService -> BaseService inheritance."""
        _, edges = playground_graph
        inherits = [e for e in edges if e.kind == EdgeKind.INHERITS]
        targets = {e.target for e in inherits}
        assert "BaseService" in targets

    def test_local_imports_captured(self, playground_graph):
        """Verify imports inside local_imports_example (json, itertools) are found."""
        _, edges = playground_graph
        import_targets = {e.target for e in edges if e.kind == EdgeKind.IMPORTS}
        assert "json" in import_targets
        assert "itertools" in import_targets

    def test_chained_calls_captured(self, playground_graph):
        """Verify chained_calls_example captures repo.get, user.to_dict, .get."""
        _, edges = playground_graph
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        chained_calls = [e for e in calls if "chained_calls_example" in e.source]
        callees = {e.target for e in chained_calls}
        assert "get" in callees
        assert "to_dict" in callees

    def test_module_level_calls_from_main_block(self, playground_graph):
        """Verify __main__ block calls (Path, FileService, process, info) are captured."""
        _, edges = playground_graph
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        module_calls = [
            e for e in calls if e.source.endswith("tree_sitter_playground.py")
        ]
        callees = {e.target for e in module_calls}
        assert "Path" in callees
        assert "FileService" in callees
        assert "process" in callees
        assert "info" in callees


# --- Uncomment and run to print full graph (useful for exploration) ---
def test_print_graph(playground_graph):
    """Print nodes and edges for manual inspection."""
    nodes, edges = playground_graph
    print("\n=== NODES ===")
    for n in sorted(nodes, key=lambda x: (x.kind.value, x.qualified_name)):
        print(f"  {n.kind.value:8} {n.qualified_name}")
    print("\n=== EDGES ===")
    for kind in EdgeKind:
        kind_edges = [e for e in edges if e.kind == kind]
        if kind_edges:
            print(f"\n  {kind.value}:")
            for e in kind_edges:
                print(f"    {e.source} -> {e.target}")
