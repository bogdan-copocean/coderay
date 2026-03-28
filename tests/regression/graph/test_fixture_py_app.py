"""Strict graph integration contracts for python fixture app."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.builder import build_graph

REPO_ROOT = Path(__file__).parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _collect_files(base: Path) -> list[tuple[str, str]]:
    """Collect source files from fixture app."""
    files: list[tuple[str, str]] = []
    for path in sorted(base.rglob("*")):
        if path.suffix == ".py":
            rel = path.relative_to(REPO_ROOT).as_posix()
            files.append((rel, path.read_text(encoding="utf-8")))
    return files


def _edge_list(graph_dict: dict) -> list[tuple[str, str, str]]:
    """Return normalized edge tuples preserving duplicates."""
    return [
        (edge["kind"], edge["source"], edge["target"]) for edge in graph_dict["edges"]
    ]


def _edges_from_file(
    edges: list[tuple[str, str, str]], file_prefix: str
) -> list[tuple[str, str, str]]:
    """Return edges whose source is in `file_prefix`."""
    return [e for e in edges if e[1].startswith(file_prefix)]


def _assert_user_service_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `user_service.py`."""
    expected_nodes = [
        ("tests/fixtures/py/app/services/user_service.py", NodeKind.MODULE.value),
        (
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
            NodeKind.CLASS.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter.format",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::UserService",
            NodeKind.CLASS.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::UserService.__init__",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter.formatter",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_user_service_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `user_service.py`."""
    expected_edges = [
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
            "tests/fixtures/py/app/core/decorators.py::trace",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/core/decorators.py::trace",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.__init__",
            "tests/fixtures/py/app/services/file_service.py::FileService",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.__init__",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.get_by_id",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/file_service.py::FileService.process_payload",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/internal/formatters.py::format_public_name",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/internal/formatters.py::format_score",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/internal/lazy_io.py::to_json_line",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/internal/lazy_io.py::summarize_totals",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter.format",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
            "tests/fixtures/py/app/services/internal/async_tasks.py::enrich_profile",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.get_by_id",
        ),
        # FIXME: Should resolve to User.to_dict when graph gains better resolution.
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
            "to_dict",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
            "tests/fixtures/py/app/services/user_service.py::UserService",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::UserService",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter.format",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py::UserService",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py::UserService",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py::UserService",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py::UserService",
            "tests/fixtures/py/app/services/user_service.py::UserService.__init__",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter.formatter",
        ),
        # FIXME: 3rd party package should not be included
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "collections.abc::Callable",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/core/decorators.py::trace",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/file_service.py::FileService",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/async_tasks.py::enrich_profile",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/formatters.py::format_public_name",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/formatters.py::format_score",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/lazy_io.py::summarize_totals",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/lazy_io.py::to_json_line",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_file_service_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `file_service.py`."""
    expected_nodes = [
        ("tests/fixtures/py/app/services/file_service.py", NodeKind.MODULE.value),
        (
            "tests/fixtures/py/app/services/file_service.py::FileService",
            NodeKind.CLASS.value,
        ),
        (
            "tests/fixtures/py/app/services/file_service.py::FileService.process_payload",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_file_service_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `file_service.py`."""
    expected_edges = [
        # Through super().
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/services/file_service.py::FileService.process_payload",
            "tests/fixtures/py/app/services/base_service.py::BaseService.process_payload",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/file_service.py",
            "tests/fixtures/py/app/services/file_service.py::FileService",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/file_service.py::FileService",
            "tests/fixtures/py/app/services/file_service.py::FileService.process_payload",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/file_service.py",
            "tests/fixtures/py/app/services/base_service.py::BaseService",
        ),
        (
            "inherits",
            "tests/fixtures/py/app/services/file_service.py::FileService",
            "tests/fixtures/py/app/services/base_service.py::BaseService",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_user_controller_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `user_controller.py`."""
    expected_nodes = [
        (
            "tests/fixtures/py/app/api/controllers/user_controller.py",
            NodeKind.MODULE.value,
        ),
        (
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile_async",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_user_controller_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `user_controller.py`."""
    expected_edges = [
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile",
            "tests/fixtures/py/app/api/serializers/profile_serializer.py::to_http_response",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile_async",
            "tests/fixtures/py/app/api/serializers/profile_serializer.py::to_http_response",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile_async",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/api/controllers/user_controller.py",
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/api/controllers/user_controller.py",
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile_async",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/api/controllers/user_controller.py",
            "tests/fixtures/py/app/api/serializers/profile_serializer.py::to_http_response",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/api/controllers/user_controller.py",
            "tests/fixtures/py/app/services/user_service.py::UserService",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_decorators_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `decorators.py`."""
    expected_nodes = [
        ("tests/fixtures/py/app/core/decorators.py", NodeKind.MODULE.value),
        ("tests/fixtures/py/app/core/decorators.py::audit", NodeKind.FUNCTION.value),
        (
            "tests/fixtures/py/app/core/decorators.py::audit.wrapper",
            NodeKind.FUNCTION.value,
        ),
        ("tests/fixtures/py/app/core/decorators.py::trace", NodeKind.FUNCTION.value),
        (
            "tests/fixtures/py/app/core/decorators.py::trace.inner",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_decorators_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `decorators.py`."""
    expected_edges = [
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/core/decorators.py",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/core/decorators.py",
            "tests/fixtures/py/app/core/decorators.py::trace",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/core/decorators.py::audit",
            "tests/fixtures/py/app/core/decorators.py::audit.wrapper",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/core/decorators.py::trace",
            "tests/fixtures/py/app/core/decorators.py::trace.inner",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/core/decorators.py",
            "collections.abc::Callable",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_lazy_io_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `lazy_io.py`."""
    expected_nodes = [
        ("tests/fixtures/py/app/services/internal/lazy_io.py", NodeKind.MODULE.value),
        (
            "tests/fixtures/py/app/services/internal/lazy_io.py::to_json_line",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/internal/lazy_io.py::summarize_totals",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_lazy_io_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `lazy_io.py`."""
    expected_edges = [
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/internal/lazy_io.py",
            "tests/fixtures/py/app/services/internal/lazy_io.py::summarize_totals",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/internal/lazy_io.py",
            "tests/fixtures/py/app/services/internal/lazy_io.py::to_json_line",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/internal/lazy_io.py",
            "collections::defaultdict",
        ),
        # FIXME: stdlib/3rd party lib should not be captured
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/internal/lazy_io.py::summarize_totals",
            "itertools::chain",
        ),
        # FIXME: stdlib/3rd party lib should not be captured
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/internal/lazy_io.py::to_json_line",
            "json",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_domain_models_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `models.py`."""
    expected_nodes = [
        ("tests/fixtures/py/app/domain/models.py", NodeKind.MODULE.value),
        ("tests/fixtures/py/app/domain/models.py::User", NodeKind.CLASS.value),
        (
            "tests/fixtures/py/app/domain/models.py::User.to_dict",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_domain_models_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `models.py`."""
    expected_edges = [
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/domain/models.py",
            "tests/fixtures/py/app/domain/models.py::User",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/domain/models.py::User",
            "tests/fixtures/py/app/domain/models.py::User.to_dict",
        ),
        # FIXME: stdlib/3rd party lib should not be captured
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/domain/models.py",
            "dataclasses",
        ),
        # FIXME: stdlib/3rd party lib should not be captured
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/domain/models.py",
            "dataclasses::dataclass",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_main_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `main.py`."""
    expected_nodes = [
        ("tests/fixtures/py/app/main.py", NodeKind.MODULE.value),
        ("tests/fixtures/py/app/main.py::handle_request", NodeKind.FUNCTION.value),
        (
            "tests/fixtures/py/app/main.py::handle_request_async",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_main_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `main.py`."""
    expected_edges = [
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/main.py::handle_request",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/services/file_service.py::FileService",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/services/file_service.py::FileService.process_payload",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py::handle_request",
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py::handle_request",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py::handle_request",
            "tests/fixtures/py/app/services/user_service.py::UserService",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py::handle_request_async",
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile_async",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py::handle_request_async",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
        ),
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/main.py::handle_request_async",
            "tests/fixtures/py/app/services/user_service.py::UserService",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/main.py::handle_request",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/main.py::handle_request_async",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile_async",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/services/file_service.py::FileService",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/main.py",
            "tests/fixtures/py/app/services/user_service.py::UserService",
        ),
        # FIXME: stdlib/3rd party lib should not be captured
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/main.py",
            "pathlib::Path",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_formatters_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `formatters.py`."""
    expected_nodes = [
        (
            "tests/fixtures/py/app/services/internal/formatters.py",
            NodeKind.MODULE.value,
        ),
        (
            "tests/fixtures/py/app/services/internal/formatters.py::format_public_name",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/services/internal/formatters.py::format_score",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_formatters_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `formatters.py`."""
    expected_edges = [
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/internal/formatters.py",
            "tests/fixtures/py/app/services/internal/formatters.py::format_public_name",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/internal/formatters.py",
            "tests/fixtures/py/app/services/internal/formatters.py::format_score",
        ),
        # FIXME: stdlib/3rd party lib should not be captured
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/internal/formatters.py",
            "math",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/internal/formatters.py",
            "tests/fixtures/py/app/domain/models.py::User",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_async_tasks_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `async_tasks.py`."""
    expected_nodes = [
        (
            "tests/fixtures/py/app/services/internal/async_tasks.py",
            NodeKind.MODULE.value,
        ),
        (
            "tests/fixtures/py/app/services/internal/async_tasks.py::enrich_profile",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_async_tasks_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `async_tasks.py`."""
    expected_edges = [
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/services/internal/async_tasks.py",
            "tests/fixtures/py/app/services/internal/async_tasks.py::enrich_profile",
        ),
        # FIXME: stdlib/3rd party lib should not be captured
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/services/internal/async_tasks.py",
            "asyncio",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_user_repository_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `user_repository.py`."""
    expected_nodes = [
        (
            "tests/fixtures/py/app/infra/repositories/user_repository.py",
            NodeKind.MODULE.value,
        ),
        (
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
            NodeKind.CLASS.value,
        ),
        (
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.__init__",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.get_by_id",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_user_repository_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `user_repository.py`."""
    expected_edges = [
        # FIXME: Missing inherit edge between UserRepository and BaseRepository
        (
            EdgeKind.CALLS,
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.__init__",
            "tests/fixtures/py/app/domain/models.py::User",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/infra/repositories/user_repository.py",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.__init__",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.get_by_id",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/infra/repositories/user_repository.py",
            "tests/fixtures/py/app/domain/models.py::User",
        ),
        (
            EdgeKind.IMPORTS,
            "tests/fixtures/py/app/infra/repositories/user_repository.py",
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


def _assert_base_repository_nodes(nodes: list[tuple[str, dict]]) -> None:
    """Assert expected nodes for `base_repository.py`."""
    expected_nodes = [
        (
            "tests/fixtures/py/app/infra/repositories/base_repository.py",
            NodeKind.MODULE.value,
        ),
        (
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository",
            NodeKind.CLASS.value,
        ),
        (
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository.__init__",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository.add",
            NodeKind.FUNCTION.value,
        ),
        (
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository.get",
            NodeKind.FUNCTION.value,
        ),
    ]
    computed_nodes: list[tuple[str, str]] = []
    for node_id, data in nodes:
        graph_node = data["data"]
        assert node_id == graph_node.id
        computed_nodes.append((node_id, graph_node.kind.value))
    assert len(computed_nodes) == len(expected_nodes)
    assert Counter(computed_nodes) == Counter(expected_nodes)


def _assert_base_repository_edges(computed_edges: list[tuple[str, str, str]]) -> None:
    """Assert expected edges for `base_repository.py`."""
    expected_edges = [
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/infra/repositories/base_repository.py",
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository",
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository.__init__",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository",
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository.add",
        ),
        (
            EdgeKind.DEFINES,
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository",
            "tests/fixtures/py/app/infra/repositories/base_repository.py::BaseRepository.get",
        ),
    ]
    assert len(computed_edges) == len(expected_edges)
    assert Counter(computed_edges) == Counter(expected_edges)


class TestPyAppGraphContracts:
    def test_py_app_user_service(self) -> None:
        user_service_prefix = "tests/fixtures/py/app/services/user_service.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_user_service_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(user_service_prefix)
        ]

        _assert_user_service_nodes(computed_user_service_nodes)
        computed_edges = _edges_from_file(
            _edge_list(graph.to_dict()), user_service_prefix
        )
        _assert_user_service_edges(computed_edges)

    def test_py_app_file_service(self) -> None:
        file_service_prefix = "tests/fixtures/py/app/services/file_service.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_file_service_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(file_service_prefix)
        ]

        _assert_file_service_nodes(computed_file_service_nodes)
        computed_edges = _edges_from_file(
            _edge_list(graph.to_dict()), file_service_prefix
        )
        _assert_file_service_edges(computed_edges)

    def test_py_app_user_controller(self) -> None:
        controller_prefix = "tests/fixtures/py/app/api/controllers/user_controller.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_controller_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(controller_prefix)
        ]

        _assert_user_controller_nodes(computed_controller_nodes)
        computed_edges = _edges_from_file(
            _edge_list(graph.to_dict()), controller_prefix
        )
        _assert_user_controller_edges(computed_edges)

    def test_py_app_decorators(self) -> None:
        decorators_prefix = "tests/fixtures/py/app/core/decorators.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_decorators_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(decorators_prefix)
        ]

        _assert_decorators_nodes(computed_decorators_nodes)
        computed_edges = _edges_from_file(
            _edge_list(graph.to_dict()), decorators_prefix
        )
        _assert_decorators_edges(computed_edges)

    def test_py_app_lazy_io(self) -> None:
        lazy_io_prefix = "tests/fixtures/py/app/services/internal/lazy_io.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_lazy_io_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(lazy_io_prefix)
        ]

        _assert_lazy_io_nodes(computed_lazy_io_nodes)
        computed_edges = _edges_from_file(_edge_list(graph.to_dict()), lazy_io_prefix)
        _assert_lazy_io_edges(computed_edges)

    def test_py_app_domain_models(self) -> None:
        models_prefix = "tests/fixtures/py/app/domain/models.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_models_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(models_prefix)
        ]

        _assert_domain_models_nodes(computed_models_nodes)
        computed_edges = _edges_from_file(_edge_list(graph.to_dict()), models_prefix)
        _assert_domain_models_edges(computed_edges)

    def test_py_app_main(self) -> None:
        main_prefix = "tests/fixtures/py/app/main.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_main_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(main_prefix)
        ]

        _assert_main_nodes(computed_main_nodes)
        computed_edges = _edges_from_file(_edge_list(graph.to_dict()), main_prefix)
        _assert_main_edges(computed_edges)

    def test_py_app_formatters(self) -> None:
        formatters_prefix = "tests/fixtures/py/app/services/internal/formatters.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_formatters_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(formatters_prefix)
        ]

        _assert_formatters_nodes(computed_formatters_nodes)
        computed_edges = _edges_from_file(
            _edge_list(graph.to_dict()), formatters_prefix
        )
        _assert_formatters_edges(computed_edges)

    def test_py_app_async_tasks(self) -> None:
        async_tasks_prefix = "tests/fixtures/py/app/services/internal/async_tasks.py"
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_async_tasks_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(async_tasks_prefix)
        ]

        _assert_async_tasks_nodes(computed_async_tasks_nodes)
        computed_edges = _edges_from_file(
            _edge_list(graph.to_dict()), async_tasks_prefix
        )
        _assert_async_tasks_edges(computed_edges)

    def test_py_app_user_repository(self) -> None:
        user_repository_prefix = (
            "tests/fixtures/py/app/infra/repositories/user_repository.py"
        )
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_user_repository_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(user_repository_prefix)
        ]

        _assert_user_repository_nodes(computed_user_repository_nodes)
        computed_edges = _edges_from_file(
            _edge_list(graph.to_dict()), user_repository_prefix
        )
        _assert_user_repository_edges(computed_edges)

    def test_py_app_base_repository(self) -> None:
        base_repository_prefix = (
            "tests/fixtures/py/app/infra/repositories/base_repository.py"
        )
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        computed_base_repository_nodes = [
            node
            for node in graph._g.nodes(data=True)
            if node[0].startswith(base_repository_prefix)
        ]

        _assert_base_repository_nodes(computed_base_repository_nodes)
        computed_edges = _edges_from_file(
            _edge_list(graph.to_dict()), base_repository_prefix
        )
        _assert_base_repository_edges(computed_edges)
