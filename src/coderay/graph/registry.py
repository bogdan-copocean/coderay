"""Graph plugin registry keyed by language name."""

from __future__ import annotations

from coderay.graph.plugin_protocol import LanguageGraphPlugin

_PLUGINS: dict[str, LanguageGraphPlugin] = {}


def register_graph_plugin(plugin: LanguageGraphPlugin) -> None:
    """Register a language plugin."""
    _PLUGINS[plugin.language_id] = plugin


def get_graph_plugin(language_id: str) -> LanguageGraphPlugin | None:
    """Return plugin for language name from ParserContext.lang_cfg.name."""
    return _PLUGINS.get(language_id)


def ensure_plugins_loaded() -> None:
    """Import plugins once so they self-register."""
    import coderay.graph.plugins.js_ts  # noqa: F401
    import coderay.graph.plugins.python  # noqa: F401
