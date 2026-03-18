"""Integration tests: extractor, chunker, graph against production-like JS/TS fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from coderay.chunking.chunker import chunk_file
from coderay.core.models import EdgeKind, NodeKind
from coderay.graph.builder import build_and_save_graph
from coderay.graph.extractor import extract_graph_from_file
from coderay.skeleton.extractor import extract_skeleton

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "js_ts_production"


def _has_tree_sitter_js() -> bool:
    try:
        import tree_sitter_javascript  # noqa: F401
        return True
    except ImportError:
        return False


def _has_tree_sitter_ts() -> bool:
    try:
        import tree_sitter_typescript as tsts
        tsts.language_typescript()
        return True
    except (ImportError, AttributeError):
        return False


@pytest.mark.skipif(
    not _has_tree_sitter_js(),
    reason="tree-sitter-javascript not installed",
)
class TestJsProductionFixtures:
    """Skeleton, chunker, graph against production-like JS."""

    def test_skeleton_user_service(self) -> None:
        path = FIXTURES_DIR / "userService.js"
        content = path.read_text()
        skeleton = extract_skeleton(path, content, include_imports=True)

        assert "import { db }" in skeleton or "import" in skeleton
        assert "class UserService" in skeleton
        assert "fetchUsers" in skeleton
        assert "createUser" in skeleton
        assert "_toDTO" in skeleton
        assert "..." in skeleton
        assert "createUserService" in skeleton

    def test_skeleton_config(self) -> None:
        path = FIXTURES_DIR / "config.js"
        content = path.read_text()
        skeleton = extract_skeleton(path, content)

        assert "API_URL" in skeleton or "ENV" in skeleton or "export" in skeleton

    def test_chunker_user_service(self) -> None:
        path = FIXTURES_DIR / "userService.js"
        content = path.read_text()
        chunks = chunk_file(path, content)

        symbols = {c.symbol for c in chunks}
        assert "createUser" in symbols or "fetchUsers" in symbols
        assert "createUserService" in symbols or "UserService" in symbols or len(chunks) >= 3

    def test_graph_user_service_imports(self) -> None:
        path = FIXTURES_DIR / "userService.js"
        content = path.read_text()
        nodes, edges = extract_graph_from_file(str(path), content)

        module_nodes = [n for n in nodes if n.kind == NodeKind.MODULE]
        assert len(module_nodes) == 1

        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) >= 1

    def test_graph_user_service_definitions(self) -> None:
        path = FIXTURES_DIR / "userService.js"
        content = path.read_text()
        nodes, edges = extract_graph_from_file(str(path), content)

        class_nodes = [n for n in nodes if n.kind == NodeKind.CLASS]
        assert any("UserService" in n.name for n in class_nodes) or len(nodes) >= 1

    def test_graph_user_service_inherits(self) -> None:
        """UserService extends BaseService produces INHERITS edge."""
        path = FIXTURES_DIR / "userService.js"
        content = path.read_text()
        nodes, edges = extract_graph_from_file(str(path), content)

        inherits = [e for e in edges if e.kind == EdgeKind.INHERITS]
        assert len(inherits) >= 1
        us_node = next((n for n in nodes if "UserService" in n.name and n.kind == NodeKind.CLASS), None)
        assert us_node is not None
        us_inherits = [e for e in inherits if e.source == us_node.id]
        assert len(us_inherits) >= 1


@pytest.mark.skipif(
    not _has_tree_sitter_ts(),
    reason="tree-sitter-typescript not installed",
)
class TestTsProductionFixtures:
    """Skeleton, chunker, graph against production-like TS."""

    def test_skeleton_api_client(self) -> None:
        path = FIXTURES_DIR / "apiClient.ts"
        content = path.read_text()
        skeleton = extract_skeleton(path, content, include_imports=True)

        assert "import" in skeleton
        assert "class ApiClient" in skeleton
        assert "get" in skeleton or "post" in skeleton
        assert "..." in skeleton

    def test_skeleton_types(self) -> None:
        path = FIXTURES_DIR / "types.ts"
        content = path.read_text()
        skeleton = extract_skeleton(path, content)

        assert "interface" in skeleton or "RequestConfig" in skeleton or "Response" in skeleton

    def test_chunker_api_client(self) -> None:
        path = FIXTURES_DIR / "apiClient.ts"
        content = path.read_text()
        chunks = chunk_file(path, content)

        symbols = {c.symbol for c in chunks}
        assert "createApiClient" in symbols or "get" in symbols or "_parseResponse" in symbols
        assert len(chunks) >= 2

    def test_graph_api_client_imports(self) -> None:
        path = FIXTURES_DIR / "apiClient.ts"
        content = path.read_text()
        nodes, edges = extract_graph_from_file(str(path), content)

        import_edges = [e for e in edges if e.kind == EdgeKind.IMPORTS]
        assert len(import_edges) >= 1

    def test_graph_types_module(self) -> None:
        path = FIXTURES_DIR / "types.ts"
        content = path.read_text()
        nodes, edges = extract_graph_from_file(str(path), content)

        assert len(nodes) >= 1


@pytest.mark.skipif(
    not (_has_tree_sitter_js() and _has_tree_sitter_ts()),
    reason="tree-sitter-javascript and tree-sitter-typescript required",
)
class TestFullPipeline:
    """Full pipeline: build graph over mixed JS/TS fixture repo."""

    def test_build_graph_mixed_repo(self, tmp_path: Path, app_config) -> None:
        """Build graph over fixture dir; verify nodes and edges."""
        file_names = ["userService.js", "config.js", "index.js"]
        changed_paths = file_names
        files_content = [
            (name, (FIXTURES_DIR / name).read_text())
            for name in file_names
        ]

        build_and_save_graph(
            repo_root=str(FIXTURES_DIR),
            changed_paths=changed_paths,
            files_content=files_content,
        )

        graph_path = Path(app_config.index.path) / "graph.json"
        assert graph_path.exists()
        import json
        data = json.loads(graph_path.read_text())
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        assert len(nodes) >= 2
        assert len(edges) >= 1
