"""Tests for indexer.chunking.chunker."""

from coderay.chunking.chunker import chunk_file


class TestChunkFile:
    def test_single_function(self):
        code = "def hello():\n    return 'hi'\n"
        chunks = chunk_file("test.py", code)
        fn_chunks = [c for c in chunks if c.symbol == "hello"]
        assert len(fn_chunks) == 1
        assert fn_chunks[0].path == "test.py"

    def test_class_and_method(self, sample_python_code):
        chunks = chunk_file("sample.py", sample_python_code)
        symbols = {c.symbol for c in chunks}
        assert "Greeter" in symbols

    def test_empty_file(self):
        chunks = chunk_file("empty.py", "")
        assert chunks == []

    def test_non_python(self):
        chunks = chunk_file("test.js", "function foo() {}")
        try:
            import tree_sitter_javascript  # noqa: F401

            assert len(chunks) >= 1
        except ImportError:
            assert chunks == []

    def test_no_expression_statement_chunks(self):
        code = "x = 1\ny = 2\ndef foo():\n    pass\n"
        chunks = chunk_file("test.py", code)
        symbols = {c.symbol for c in chunks}
        assert "x = 1" not in symbols
        assert "y = 2" not in symbols

    def test_preamble_chunk_generated(self):
        code = "import os\nfrom pathlib import Path\n\ndef foo():\n    pass\n"
        chunks = chunk_file("test.py", code)
        preamble = [c for c in chunks if c.symbol == "<module>"]
        assert len(preamble) == 1
        assert "import os" in preamble[0].content
        assert "from pathlib import Path" in preamble[0].content

    def test_preamble_excludes_definitions(self):
        code = "import os\n\ndef foo():\n    pass\n\nclass Bar:\n    pass\n"
        chunks = chunk_file("test.py", code)
        preamble = [c for c in chunks if c.symbol == "<module>"]
        assert len(preamble) == 1
        assert "def foo" not in preamble[0].content
        assert "class Bar" not in preamble[0].content

    def test_no_preamble_when_only_definitions(self):
        code = "def foo():\n    pass\n"
        chunks = chunk_file("test.py", code)
        preamble = [c for c in chunks if c.symbol == "<module>"]
        assert len(preamble) == 0

    def test_multiple_files(self):
        chunks_a = chunk_file("a.py", "def a():\n    pass\n")
        chunks_b = chunk_file("b.py", "def b():\n    pass\n")
        symbols = {c.symbol for c in chunks_a + chunks_b}
        assert "a" in symbols
        assert "b" in symbols


class TestDecoratedDefinitions:
    """Verify decorated functions/classes produce correct chunks."""

    def test_single_decorator_function(self):
        code = "@staticmethod\ndef my_func():\n    return 42\n"
        chunks = chunk_file("test.py", code)
        non_preamble = [c for c in chunks if c.symbol != "<module>"]
        assert len(non_preamble) == 1, (
            f"Expected 1 chunk for decorated function, got {len(non_preamble)}: "
            f"{[c.symbol for c in non_preamble]}"
        )
        assert non_preamble[0].symbol == "my_func"
        assert "@staticmethod" in non_preamble[0].content
        assert "def my_func" in non_preamble[0].content

    def test_single_decorator_class(self):
        code = "@dataclass\nclass Config:\n    name: str = 'default'\n"
        chunks = chunk_file("test.py", code)
        non_preamble = [c for c in chunks if c.symbol != "<module>"]
        assert len(non_preamble) == 1, (
            f"Expected 1 chunk for decorated class, got {len(non_preamble)}: "
            f"{[c.symbol for c in non_preamble]}"
        )
        assert non_preamble[0].symbol == "Config"
        assert "@dataclass" in non_preamble[0].content
        assert "class Config" in non_preamble[0].content

    def test_multiple_decorators_stacked(self):
        code = (
            "@app.route('/api')\n@login_required\ndef api_handler():\n    return 'ok'\n"
        )
        chunks = chunk_file("test.py", code)
        non_preamble = [c for c in chunks if c.symbol != "<module>"]
        assert len(non_preamble) == 1, (
            f"Expected 1 chunk for multi-decorated function, got {len(non_preamble)}: "
            f"{[c.symbol for c in non_preamble]}"
        )
        assert non_preamble[0].symbol == "api_handler"
        assert "@app.route" in non_preamble[0].content
        assert "@login_required" in non_preamble[0].content

    def test_decorator_symbol_is_function_name_not_decorator_name(self):
        code = "@cache\ndef expensive_calc(n):\n    return n ** 2\n"
        chunks = chunk_file("test.py", code)
        symbols = {c.symbol for c in chunks}
        assert "expensive_calc" in symbols
        assert "cache" not in symbols

    def test_decorated_not_in_preamble(self):
        code = "import os\n\n@staticmethod\ndef my_func():\n    return 42\n"
        chunks = chunk_file("test.py", code)
        preamble = [c for c in chunks if c.symbol == "<module>"]
        assert len(preamble) == 1
        assert "@staticmethod" not in preamble[0].content
        assert "def my_func" not in preamble[0].content
