"""Tests for multi-language registry."""

from coderay.parsing.languages import (
    LANGUAGE_REGISTRY,
    get_language_for_file,
    get_supported_extensions,
)


class TestLanguageRegistry:
    def test_python_registered(self):
        assert "python" in LANGUAGE_REGISTRY
        cfg = LANGUAGE_REGISTRY["python"]
        assert ".py" in cfg.extensions
        assert "function_definition" in cfg.chunker.chunk_types

    def test_javascript_registered(self):
        assert "javascript" in LANGUAGE_REGISTRY
        cfg = LANGUAGE_REGISTRY["javascript"]
        assert ".js" in cfg.extensions
        assert "function_declaration" in cfg.chunker.chunk_types

    def test_typescript_registered(self):
        assert "typescript" in LANGUAGE_REGISTRY
        cfg = LANGUAGE_REGISTRY["typescript"]
        assert ".ts" in cfg.extensions
        assert "interface_declaration" in cfg.chunker.chunk_types

    def test_go_registered(self):
        assert "go" in LANGUAGE_REGISTRY
        cfg = LANGUAGE_REGISTRY["go"]
        assert ".go" in cfg.extensions
        assert "function_declaration" in cfg.chunker.chunk_types


class TestGetLanguageForFile:
    def test_python_file(self):
        cfg = get_language_for_file("src/main.py")
        assert cfg is not None
        assert cfg.name == "python"

    def test_js_file(self):
        cfg = get_language_for_file("app/index.js")
        assert cfg is not None
        assert cfg.name == "javascript"

    def test_ts_file(self):
        cfg = get_language_for_file("app/index.ts")
        assert cfg is not None
        assert cfg.name == "typescript"

    def test_tsx_file(self):
        cfg = get_language_for_file("components/Button.tsx")
        assert cfg is not None
        assert cfg.name == "typescript"

    def test_go_file(self):
        cfg = get_language_for_file("cmd/main.go")
        assert cfg is not None
        assert cfg.name == "go"

    def test_unsupported_extension(self):
        assert get_language_for_file("readme.md") is None
        assert get_language_for_file("data.csv") is None

    def test_pyi_stub(self):
        cfg = get_language_for_file("types.pyi")
        assert cfg is not None
        assert cfg.name == "python"


class TestGetSupportedExtensions:
    def test_includes_common_extensions(self):
        exts = get_supported_extensions()
        assert ".py" in exts
        assert ".js" in exts
        assert ".ts" in exts
        assert ".go" in exts

    def test_includes_variants(self):
        exts = get_supported_extensions()
        assert ".jsx" in exts
        assert ".tsx" in exts
        assert ".mjs" in exts
        assert ".pyi" in exts


class TestLanguageConfigParser:
    def test_python_parser_loads(self):
        from coderay.parsing.base import BaseTreeSitterParser, ParserContext

        cfg = LANGUAGE_REGISTRY["python"]
        ctx = ParserContext(
            file_path="test.py", content="def foo(): pass", lang_cfg=cfg
        )
        parser = BaseTreeSitterParser(ctx)
        tree = parser.get_tree()
        assert tree.root_node is not None
