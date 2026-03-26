"""Strict graph integration contracts for fixture apps."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.graph.builder import build_graph

REPO_ROOT = Path(__file__).parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures"

pytestmark = pytest.mark.integration


def _collect_files(base: Path) -> list[tuple[str, str]]:
    """Collect source files from fixture app."""
    files: list[tuple[str, str]] = []
    for path in sorted(base.rglob("*")):
        if path.suffix in {".py", ".js", ".ts"}:
            rel = path.relative_to(REPO_ROOT).as_posix()
            files.append((rel, path.read_text(encoding="utf-8")))
    return files


def _edge_set(graph_dict: dict) -> set[tuple[str, str, str]]:
    """Return normalized edge tuples."""
    return {
        (edge["kind"], edge["source"], edge["target"]) for edge in graph_dict["edges"]
    }


class TestPyAppGraphContracts:
    def test_py_app_explicit_edges(self) -> None:
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "py" / "app"))
        edges = _edge_set(graph.to_dict())
        expected = {
            (
                "imports",
                "tests/fixtures/py/app/main.py",
                "tests/fixtures/py/app/services/user_service.py::UserService",
            ),
            (
                "calls",
                "tests/fixtures/py/app/main.py::handle_request",
                "tests/fixtures/py/app/api/controllers/user_controller.py::get_user_profile",
            ),
            (
                "calls",
                "tests/fixtures/py/app/services/user_service.py::UserService.load_profile",
                "tests/fixtures/py/app/services/internal/lazy_io.py::to_json_line",
            ),
            (
                "calls",
                "tests/fixtures/py/app/services/user_service.py::UserService.load_profile_async",
                "tests/fixtures/py/app/services/internal/async_tasks.py::enrich_profile",
            ),
            (
                "inherits",
                "tests/fixtures/py/app/services/file_service.py::FileService",
                "tests/fixtures/py/app/services/base_service.py::BaseService",
            ),
        }
        assert expected.issubset(edges)


class TestJsTsAppGraphContracts:
    def test_js_ts_app_explicit_edges(self) -> None:
        graph = build_graph(str(REPO_ROOT), _collect_files(FIXTURES / "js_ts" / "app"))
        edges = _edge_set(graph.to_dict())
        expected = {
            (
                "imports",
                "tests/fixtures/js_ts/app/api/http/router.js",
                "tests/fixtures/js_ts/app/services/userService.ts::UserService",
            ),
            (
                "calls",
                "tests/fixtures/js_ts/app/index.ts::startApp",
                "tests/fixtures/js_ts/app/api/http/router.js::registerRoutes",
            ),
            (
                "calls",
                "tests/fixtures/js_ts/app/services/userService.ts::UserService.loadProfile",
                "tests/fixtures/js_ts/app/services/internal/formatters.ts::formatUserLabel",
            ),
            (
                "calls",
                "tests/fixtures/js_ts/app/services/userService.ts::UserService.loadProfileAsync",
                "tests/fixtures/js_ts/app/services/internal/callbacks.ts::verifyAsync",
            ),
            (
                "imports",
                "tests/fixtures/js_ts/app/index.ts",
                "tests/fixtures/js_ts/app/services/internal/streaming.ts::StreamProcessor",
            ),
        }
        assert expected.issubset(edges)
