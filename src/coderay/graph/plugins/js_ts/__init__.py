"""JavaScript / TypeScript graph plugins."""

from coderay.graph.plugins.base.plugin import GraphPlugin
from coderay.graph.plugins.js_ts.extractor import JsTsGraphExtractor
from coderay.graph.registry import register_graph_plugin

register_graph_plugin(GraphPlugin("javascript", JsTsGraphExtractor))
register_graph_plugin(GraphPlugin("typescript", JsTsGraphExtractor))
