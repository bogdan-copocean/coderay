"""Test multi-language registry."""

import pytest

from coderay.parsing.languages import (
    LANGUAGE_REGISTRY,
    get_language_for_file,
    get_supported_extensions,
)


class TestLanguageRegistry:
    @pytest.mark.parametrize(
        "lang,ext,chunk_type",
        [
            ("python", ".py", "function_definition"),
            ("javascript", ".js", "function_declaration"),
            ("typescript", ".ts", "interface_declaration"),
            ("go", ".go", "function_declaration"),
        ],
    )
    def test_language_registered(self, lang, ext, chunk_type):
        assert lang in LANGUAGE_REGISTRY
        cfg = LANGUAGE_REGISTRY[lang]
        assert ext in cfg.extensions
        assert chunk_type in cfg.chunker.chunk_types


class TestGetLanguageForFile:
    @pytest.mark.parametrize(
        "path,expected_name",
        [
            ("src/main.py", "python"),
            ("app/index.js", "javascript"),
            ("app/index.ts", "typescript"),
            ("components/Button.tsx", "typescript"),
            ("cmd/main.go", "go"),
            ("types.pyi", "python"),
        ],
    )
    def test_resolves_language(self, path, expected_name):
        cfg = get_language_for_file(path)
        assert cfg is not None
        assert cfg.name == expected_name

    @pytest.mark.parametrize("path", ["readme.md", "data.csv"])
    def test_unsupported_extension(self, path):
        assert get_language_for_file(path) is None


class TestGetSupportedExtensions:
    @pytest.mark.parametrize(
        "ext",
        [".py", ".js", ".ts", ".go", ".jsx", ".tsx", ".mjs", ".pyi"],
    )
    def test_includes_extensions(self, ext):
        assert ext in get_supported_extensions()


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
