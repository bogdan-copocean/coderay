"""Python graph plugin."""

from coderay.graph.plugins.base.plugin import GraphPlugin
from coderay.graph.plugins.python.extractor import PythonGraphExtractor
from coderay.graph.registry import register_graph_plugin

register_graph_plugin(GraphPlugin("python", PythonGraphExtractor))
