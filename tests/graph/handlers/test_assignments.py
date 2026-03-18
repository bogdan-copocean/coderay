"""Test AssignmentHandlerMixin: aliases, injection, with-statement, unpacking."""

from pathlib import Path

from coderay.core.models import EdgeKind
from coderay.graph.extractor import extract_graph_from_file

SAMPLE_PATH = Path(__file__).parent.parent / "graph_sample.py"


def _calls_from(edges, source_fragment: str) -> set[str]:
    return {
        e.target
        for e in edges
        if e.kind == EdgeKind.CALLS and source_fragment in e.source
    }


# ---------------------------------------------------------------------------
# _handle_assignment: x = y (simple alias)
# ---------------------------------------------------------------------------


class TestSimpleAlias:
    """x = y registers alias when y resolves."""

    def test_alias_to_from_import_resolves_on_call(self):
        """my_dd = dd; my_dd(int) → collections::defaultdict."""
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_aliases")
        assert "collections::defaultdict" in targets

    def test_alias_to_class_resolves_on_call(self):
        """client_class = HttpClient; client_class() → HttpClient."""
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_aliases")
        assert any("HttpClient" in t for t in targets)

    def test_alias_to_bare_import_resolves_on_call(self):
        """path_func = Path; path_func('.') → pathlib::Path."""
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_aliases")
        assert "pathlib::Path" in targets


# ---------------------------------------------------------------------------
# _handle_assignment: x = obj.attr (attribute alias)
# ---------------------------------------------------------------------------


class TestAttributeAlias:
    """x = obj.attr when obj resolves."""

    def test_attribute_alias_registers(self):
        code = "from pathlib import Path\npath_func = Path\npath_func('.')\n"
        _, edges = extract_graph_from_file("test.py", code)
        calls = [e for e in edges if e.kind == EdgeKind.CALLS]
        targets = {e.target for e in calls}
        assert "pathlib::Path" in targets


# ---------------------------------------------------------------------------
# _handle_assignment: self.attr = param (constructor/setter injection)
# ---------------------------------------------------------------------------


class TestConstructorAndSetterInjection:
    """self.storage = storage (storage: StoragePort) registers instance."""

    def test_constructor_injection_creates_edge(self):
        """UseCaseWithInjectedStorage.execute calls self.storage.save()."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "UseCaseWithInjectedStorage.execute")
        assert f"{pg}::StoragePort.save" in targets

    def test_setter_injection_creates_edge(self):
        """ServiceWithSetterInjection.persist calls self._repo.save()."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "ServiceWithSetterInjection.persist")
        assert f"{pg}::RepositoryPort.save" in targets


# ---------------------------------------------------------------------------
# _handle_with_statement, _process_with_item: with cm() as x
# ---------------------------------------------------------------------------


class TestWithStatement:
    """with cm() as x — register x with __enter__ return type."""

    def test_context_manager_injection_resolved(self):
        """with HttpClientContext() as client: client.get() — HttpClient.get."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_client_context")
        assert f"{pg}::HttpClient.get" in targets


# ---------------------------------------------------------------------------
# _handle_tuple_unpacking: a, b = func()
# ---------------------------------------------------------------------------


class TestTupleUnpacking:
    """a, b = get_handlers() — register from return type tuple[X, Y]."""

    def test_tuple_unpacking_resolved(self):
        """first, second = get_handlers(); first.run() — FirstHandler.run."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_tuple_unpacking")
        assert f"{pg}::FirstHandler.run" in targets
        assert f"{pg}::SecondHandler.run" in targets


# ---------------------------------------------------------------------------
# functools.partial: p = partial(foo, 1); p()
# ---------------------------------------------------------------------------


class TestPartialAlias:
    """partial(foo, 1) assigns alias to foo."""

    def test_partial_resolved(self):
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_partial")
        assert f"{pg}::greeter" in targets
