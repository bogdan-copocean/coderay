"""Strict graph integration contracts for python fixture app."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from coderay.core.models import NodeKind
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
            "calls",
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
            "tests/fixtures/py/app/core/decorators.py::trace",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/core/decorators.py::trace",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.__init__",
            "tests/fixtures/py/app/services/file_service.py::FileService",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.__init__",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.get_by_id",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/file_service.py::FileService.process_payload",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/internal/formatters.py::format_public_name",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/internal/formatters.py::format_score",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/internal/lazy_io.py::to_json_line",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/internal/lazy_io.py::summarize_totals",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter.format",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
            "tests/fixtures/py/app/services/internal/async_tasks.py::enrich_profile",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository.get_by_id",
        ),
        # FIXME: Should resolve to User.to_dict when graph gains better resolution.
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
            "to_dict",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
            "tests/fixtures/py/app/services/user_service.py::UserService",
        ),
        (
            "calls",
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::UserService",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::chain_email_lookup",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::decorated_multiplier",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/user_service.py::get_formatter",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter",
            "tests/fixtures/py/app/services/user_service.py::DecoratedFormatter.format",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py::UserService",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py::UserService",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py::UserService",
            "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py::UserService",
            "tests/fixtures/py/app/services/user_service.py::UserService.__init__",
        ),
        (
            "defines",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter",
            "tests/fixtures/py/app/services/user_service.py::UserService._build_formatter.formatter",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "collections.abc::Callable",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/core/decorators.py::trace",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/core/decorators.py::audit",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/file_service.py::FileService",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/async_tasks.py::enrich_profile",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/formatters.py::format_public_name",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/formatters.py::format_score",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/lazy_io.py::summarize_totals",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/services/internal/lazy_io.py::to_json_line",
        ),
        (
            "imports",
            "tests/fixtures/py/app/services/user_service.py",
            "tests/fixtures/py/app/infra/repositories/user_repository.py::UserRepository",
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
