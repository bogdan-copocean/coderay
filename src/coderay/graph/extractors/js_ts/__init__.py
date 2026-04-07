"""JS/TS graph extractor — registers JavaScript and TypeScript plugins on import."""

from coderay.graph.extractors.js_ts.extractor import JsTsGraphExtractor
from coderay.graph.language_plugin import LanguagePlugin, register

register(LanguagePlugin("javascript", JsTsGraphExtractor))
register(LanguagePlugin("typescript", JsTsGraphExtractor))
