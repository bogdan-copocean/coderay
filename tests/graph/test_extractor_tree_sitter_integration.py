"""Basic integration tests for GraphExtractor using Tree-sitter."""

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.extractor import GraphExtractor


class TestGraphExtractor:
    def test_python_function_and_call(self) -> None:
        """Build a tiny graph with a function definition and a call."""
        code = "def foo():\n    return 1\n\nfoo()\n"
        extractor = GraphExtractor()
        nodes, edges = extractor.extract_from_file("sample.py", code)

        kinds = {n.kind for n in nodes}
        assert NodeKind.MODULE in kinds
        assert NodeKind.FUNCTION in kinds

        call_edges = [e for e in edges if e.kind == EdgeKind.CALLS]
        assert call_edges, "Expected at least one CALLS edge"
