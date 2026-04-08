"""Python graph extractor — registers the Python language plugin on import."""

from coderay.graph.extractors.python.extractor import PythonGraphExtractor
from coderay.graph.language_plugin import LanguagePlugin, register
from coderay.graph.passes.python import run_python_passes

register(LanguagePlugin("python", PythonGraphExtractor, run_python_passes))
