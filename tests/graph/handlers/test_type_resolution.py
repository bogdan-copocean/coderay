"""Tests for TypeResolutionMixin: type hint extraction and resolution.

Covers: _resolve_type_texts (union, Self, forward refs), _extract_tuple_type_args,
_get_function_return_type, _get_parameter_type_hint, factory/param/property/context.
"""

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
# _resolve_type_texts: Union (A | B)
# ---------------------------------------------------------------------------


class TestUnionTypeResolution:
    """Union types create edges to all members."""

    def test_union_type_param_creates_edges_to_both(self):
        """run_with_union_handler(handler: HandlerA | HandlerB) → both process()."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "run_with_union_handler")
        assert f"{pg}::HandlerA.process" in targets
        assert f"{pg}::HandlerB.process" in targets


# ---------------------------------------------------------------------------
# _resolve_type_texts: Self
# ---------------------------------------------------------------------------


class TestSelfTypeResolution:
    """Self resolves to enclosing class."""

    def test_self_return_type_factory_resolved(self):
        """b = Builder.create(); b.build() — Self resolves to Builder."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_self_factory")
        assert f"{pg}::Builder.build" in targets


# ---------------------------------------------------------------------------
# _get_function_return_type: factory pattern
# ---------------------------------------------------------------------------


class TestFactoryReturnType:
    """x = create_client() — return type of create_client."""

    def test_factory_return_type_resolved(self):
        """client = create_http_client(); client.get() → HttpClient.get."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_factory_client")
        assert f"{pg}::HttpClient.get" in targets


# ---------------------------------------------------------------------------
# _get_parameter_type_hint: param injection
# ---------------------------------------------------------------------------


class TestParameterTypeHint:
    """def f(processor: DataProcessor) — processor.process() resolves."""

    def test_param_injection_creates_edge(self):
        """process_with_injected_dependency(processor: DataProcessor) calls processor.process()."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "process_with_injected_dependency")
        assert f"{pg}::DataProcessor.process" in targets


# ---------------------------------------------------------------------------
# _get_return_type_from_func_node: @property return type
# ---------------------------------------------------------------------------


class TestPropertyReturnType:
    """@property def repo() -> Repo — self.repo.save() resolves."""

    def test_property_injection_creates_edge(self):
        """ServiceWithLazyRepo.do_work calls self.repo.save()."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "ServiceWithLazyRepo.do_work")
        assert f"{pg}::RepositoryPort.save" in targets


# ---------------------------------------------------------------------------
# _get_function_return_type: __enter__ for context manager
# ---------------------------------------------------------------------------


class TestContextManagerEnterReturn:
    """with cm() as x — x gets cm.__enter__ return type."""

    def test_context_manager_enter_return_resolved(self):
        """with HttpClientContext() as client: client.get()."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_client_context")
        assert f"{pg}::HttpClient.get" in targets


# ---------------------------------------------------------------------------
# _extract_tuple_type_args: tuple[X, Y] for unpacking
# ---------------------------------------------------------------------------


class TestTupleTypeArgs:
    """tuple[FirstHandler, SecondHandler] for a, b = get_handlers()."""

    def test_tuple_unpacking_from_return_type(self):
        """first, second = get_handlers(); first.run() — FirstHandler.run."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_tuple_unpacking")
        assert f"{pg}::FirstHandler.run" in targets
        assert f"{pg}::SecondHandler.run" in targets


# ---------------------------------------------------------------------------
# _find_method_in_class: classmethod factory
# ---------------------------------------------------------------------------


class TestClassmethodFactory:
    """ApiClient.create() — classmethod return type."""

    def test_classmethod_factory_resolved(self):
        """client = ApiClient.create(); client.request() — ApiClient.request."""
        pg = str(SAMPLE_PATH)
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "use_classmethod_factory")
        assert f"{pg}::ApiClient.request" in targets


# ---------------------------------------------------------------------------
# Callable injection: callback()
# ---------------------------------------------------------------------------


class TestCallableInjection:
    """run_with_callback(callback) calls callback()."""

    def test_callable_injection_creates_edge(self):
        content = SAMPLE_PATH.read_text()
        _, edges = extract_graph_from_file(str(SAMPLE_PATH), content)
        targets = _calls_from(edges, "run_with_callback")
        assert len(targets) > 0
